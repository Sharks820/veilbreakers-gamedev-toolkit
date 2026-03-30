"""C# audio template generators for Unity audio system setup.

Each function returns a complete C# source string that can be written to
a Unity project. Editor scripts go to Assets/Editor/Generated/Audio/ and
register as MenuItem commands under "VeilBreakers/Audio/...". Runtime
scripts go to Assets/Scripts/Runtime/Audio/.

All generated scripts are marked with VeilBreakers namespace comments
for identification.
"""

from __future__ import annotations

from ._cs_sanitize import sanitize_cs_identifier


def generate_footstep_manager_script(
    surfaces: list[str] | None = None,
) -> str:
    """Generate C# footstep manager with surface-to-sound mapping.

    Creates both a ScriptableObject sound bank and a MonoBehaviour manager
    that plays footstep sounds based on surface type detection.

    Args:
        surfaces: List of surface type names. Defaults to
                  ["stone", "wood", "grass", "metal", "water"].

    Returns:
        Complete C# source string.
    """
    if surfaces is None:
        surfaces = ["stone", "wood", "grass", "metal", "water"]

    surface_entries = ""
    for surface in surfaces:
        cap = surface.capitalize()
        surface_entries += f"""
        [Header("{cap}")]
        public AudioClip[] {surface.lower()}Clips;"""

    surface_cases = ""
    for surface in surfaces:
        surface_cases += f"""
            case "{surface.lower()}":
                clips = soundBank.{surface.lower()}Clips;
                break;"""

    return f'''// VeilBreakers Auto-Generated: Footstep Manager
// Surface-material footstep system with ScriptableObject sound banks
using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// ScriptableObject containing footstep AudioClip arrays per surface type.
/// Create via Assets > Create > VeilBreakers > Audio > Footstep Sound Bank.
/// </summary>
[CreateAssetMenu(fileName = "FootstepSoundBank", menuName = "VeilBreakers/Audio/Footstep Sound Bank")]
public class VeilBreakers_FootstepSoundBank : ScriptableObject
{{{surface_entries}
}}

/// <summary>
/// Footstep manager that plays surface-appropriate footstep sounds.
/// Attach to the player character and assign a FootstepSoundBank.
/// Detects surface type via Raycast and PhysicMaterial name matching.
/// </summary>
public class VeilBreakers_FootstepManager : MonoBehaviour
{{
    [Header("Configuration")]
    public VeilBreakers_FootstepSoundBank soundBank;
    public float footstepInterval = 0.4f;
    public float raycastDistance = 1.5f;
    public LayerMask groundLayer = ~0;

    [Header("Audio")]
    public AudioSource audioSource;

    private float _nextFootstepTime;
    private string _lastSurface = "stone";

    private void Awake()
    {{
        if (audioSource == null)
            audioSource = GetComponent<AudioSource>();
        if (audioSource == null)
            audioSource = gameObject.AddComponent<AudioSource>();

        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 1.0f;
    }}

    /// <summary>
    /// Call this from animation events or a movement controller.
    /// </summary>
    public void PlayFootstep()
    {{
        PlayFootstep(DetectSurface());
    }}

    /// <summary>
    /// Play a footstep sound for the specified surface type.
    /// </summary>
    /// <param name="surfaceType">Surface name (e.g., "stone", "wood", "grass").</param>
    public void PlayFootstep(string surfaceType)
    {{
        if (soundBank == null || audioSource == null) return;
        if (Time.time < _nextFootstepTime) return;

        AudioClip[] clips = null;
        switch (surfaceType.ToLower())
        {{{surface_cases}
            default:
                clips = soundBank.{surfaces[0].lower()}Clips;
                break;
        }}

        if (clips != null && clips.Length > 0)
        {{
            AudioClip clip = clips[Random.Range(0, clips.Length)];
            audioSource.pitch = Random.Range(0.9f, 1.1f);
            audioSource.PlayOneShot(clip);
            _nextFootstepTime = Time.time + footstepInterval;
        }}
    }}

    private string DetectSurface()
    {{
        if (Physics.Raycast(transform.position, Vector3.down, out RaycastHit hit, raycastDistance, groundLayer))
        {{
            if (hit.collider.sharedMaterial != null)
            {{
                string matName = hit.collider.sharedMaterial.name.ToLower();
{_generate_surface_detection(surfaces)}
            }}
        }}
        return _lastSurface;
    }}
}}
'''


def _generate_surface_detection(surfaces: list[str]) -> str:
    """Generate surface detection if-else chain for footstep manager."""
    lines = []
    for i, surface in enumerate(surfaces):
        keyword = "if" if i == 0 else "else if"
        lines.append(
            f'                {keyword} (matName.Contains("{surface.lower()}"))\n'
            f'                {{ _lastSurface = "{surface.lower()}"; return _lastSurface; }}'
        )
    return "\n".join(lines)


def generate_adaptive_music_script(
    layers: list[str] | None = None,
) -> str:
    """Generate C# adaptive music manager with layered AudioSources.

    Creates a MonoBehaviour that manages multiple audio layers and
    crossfades between them based on game state transitions.

    Args:
        layers: List of music layer/state names. Defaults to
                ["Exploration", "Combat", "Boss", "Town", "Stealth"].

    Returns:
        Complete C# source string.
    """
    if layers is None:
        layers = ["Exploration", "Combat", "Boss", "Town", "Stealth"]

    enum_entries = ",\n        ".join(layers)

    layer_init = ""
    for i, layer in enumerate(layers):
        layer_init += f"""
            // Layer {i}: {layer}
            _layers[{i}] = gameObject.AddComponent<AudioSource>();
            _layers[{i}].loop = true;
            _layers[{i}].playOnAwake = false;
            _layers[{i}].volume = {"1.0f" if i == 0 else "0.0f"};
            _layers[{i}].spatialBlend = 0.0f; // 2D music"""

    return f'''// VeilBreakers Auto-Generated: Adaptive Music Manager
// Layered music system responding to game state changes
using UnityEngine;
using System.Collections;

/// <summary>
/// Game states that drive adaptive music layer mixing.
/// </summary>
public enum GameState
{{
    {enum_entries}
}}

/// <summary>
/// Adaptive music manager with layered AudioSources.
/// Each GameState maps to an audio layer that crossfades in/out.
/// Assign AudioClips via the inspector or at runtime.
/// </summary>
public class VeilBreakers_AdaptiveMusicManager : MonoBehaviour
{{
    [Header("Music Clips (one per GameState)")]
    public AudioClip[] musicClips = new AudioClip[{len(layers)}];

    [Header("Crossfade Settings")]
    public float crossfadeDuration = 2.0f;

    private AudioSource[] _layers;
    private GameState _currentState = GameState.{layers[0]};
    private Coroutine _crossfadeCoroutine;

    private static VeilBreakers_AdaptiveMusicManager _instance;
    public static VeilBreakers_AdaptiveMusicManager Instance => _instance;

    private void Awake()
    {{
        if (_instance != null && _instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        _instance = this;
        DontDestroyOnLoad(gameObject);

        _layers = new AudioSource[{len(layers)}];
{layer_init}
    }}

    private void Start()
    {{
        // Assign clips and start the default layer
        for (int i = 0; i < musicClips.Length && i < _layers.Length; i++)
        {{
            if (musicClips[i] != null)
            {{
                _layers[i].clip = musicClips[i];
                _layers[i].Play();
            }}
        }}
    }}

    /// <summary>
    /// Transition to a new game state with crossfade.
    /// </summary>
    public void SetGameState(GameState newState)
    {{
        if (newState == _currentState) return;

        GameState oldState = _currentState;
        _currentState = newState;

        if (_crossfadeCoroutine != null)
            StopCoroutine(_crossfadeCoroutine);

        _crossfadeCoroutine = StartCoroutine(
            CrossfadeLayers((int)oldState, (int)newState)
        );
    }}

    private IEnumerator CrossfadeLayers(int fromIndex, int toIndex)
    {{
        float elapsed = 0f;
        float startVolumeFrom = _layers[fromIndex].volume;
        float startVolumeTo = _layers[toIndex].volume;

        while (elapsed < crossfadeDuration)
        {{
            elapsed += Time.unscaledDeltaTime;
            float t = Mathf.Clamp01(elapsed / crossfadeDuration);

            _layers[fromIndex].volume = Mathf.Lerp(startVolumeFrom, 0f, t);
            _layers[toIndex].volume = Mathf.Lerp(startVolumeTo, 1f, t);

            yield return null;
        }}

        _layers[fromIndex].volume = 0f;
        _layers[toIndex].volume = 1f;
    }}
}}
'''


def generate_audio_zone_script(
    zone_type: str = "cave",
    reverb_preset: str | None = None,
) -> str:
    """Generate C# editor script that creates an AudioReverbZone.

    Creates an editor command that instantiates a GameObject with
    AudioReverbZone configured for the specified environment type.

    Args:
        zone_type: Environment type -- "cave", "outdoor", "indoor",
                   "dungeon", or "forest".
        reverb_preset: Optional custom reverb preset name. If None, uses
                       zone_type defaults.

    Returns:
        Complete C# source string.
    """
    # Reverb parameter presets per zone type
    presets = {
        "cave": {
            "decayTime": "3.9f",
            "reverbDelay": "0.011f",
            "room": "-1000",
            "roomHF": "-300",
            "reflections": "-602",
            "reverb": "200",
            "minDistance": "5.0f",
            "maxDistance": "30.0f",
        },
        "outdoor": {
            "decayTime": "1.5f",
            "reverbDelay": "0.003f",
            "room": "-1800",
            "roomHF": "-1100",
            "reflections": "-400",
            "reverb": "-700",
            "minDistance": "10.0f",
            "maxDistance": "50.0f",
        },
        "indoor": {
            "decayTime": "1.5f",
            "reverbDelay": "0.007f",
            "room": "-1000",
            "roomHF": "-454",
            "reflections": "-1646",
            "reverb": "53",
            "minDistance": "3.0f",
            "maxDistance": "15.0f",
        },
        "dungeon": {
            "decayTime": "4.5f",
            "reverbDelay": "0.015f",
            "room": "-800",
            "roomHF": "-200",
            "reflections": "-500",
            "reverb": "300",
            "minDistance": "5.0f",
            "maxDistance": "35.0f",
        },
        "forest": {
            "decayTime": "1.2f",
            "reverbDelay": "0.005f",
            "room": "-2000",
            "roomHF": "-800",
            "reflections": "-300",
            "reverb": "-500",
            "minDistance": "8.0f",
            "maxDistance": "40.0f",
        },
    }

    params = presets.get(zone_type, presets["cave"])
    zone_label = zone_type.capitalize()

    return f'''// VeilBreakers Auto-Generated: Audio Reverb Zone ({zone_label})
// Creates AudioReverbZone for {zone_label} environment
using UnityEngine;
using UnityEditor;

public static class VeilBreakers_AudioZone_{zone_label}
{{
    [MenuItem("VeilBreakers/Audio/Create {zone_label} Reverb Zone")]
    public static void Execute()
    {{
        // Create a new GameObject with AudioReverbZone
        GameObject zoneObj = new GameObject("VB_ReverbZone_{zone_label}");
        AudioReverbZone reverbZone = zoneObj.AddComponent<AudioReverbZone>();

        // Configure reverb parameters for {zone_label} environment
        reverbZone.decayTime = {params["decayTime"]};
        reverbZone.reverbDelay = {params["reverbDelay"]};
        reverbZone.room = {params["room"]};
        reverbZone.roomHF = {params["roomHF"]};
        reverbZone.reflections = {params["reflections"]};
        reverbZone.reverb = {params["reverb"]};
        reverbZone.minDistance = {params["minDistance"]};
        reverbZone.maxDistance = {params["maxDistance"]};

        // Position at scene view camera for convenience
        if (SceneView.lastActiveSceneView != null)
        {{
            zoneObj.transform.position = SceneView.lastActiveSceneView.camera.transform.position;
        }}

        // Select the new object
        Selection.activeGameObject = zoneObj;
        Undo.RegisterCreatedObjectUndo(zoneObj, "Create {zone_label} Reverb Zone");

        Debug.Log("[VeilBreakers] Created {zone_label} reverb zone: " + zoneObj.name);
    }}
}}
'''


def generate_audio_mixer_setup_script(
    groups: list[str] | None = None,
) -> str:
    """Generate C# editor script that configures an AudioMixer.

    Creates an editor command that loads a template AudioMixer asset
    and configures group volumes. Since AudioMixer cannot be created
    programmatically, this script works with an existing mixer asset.

    Args:
        groups: List of mixer group names. Defaults to
                ["Master", "SFX", "Music", "Voice", "Ambient", "UI"].

    Returns:
        Complete C# source string.
    """
    if groups is None:
        groups = ["Master", "SFX", "Music", "Voice", "Ambient", "UI"]

    group_configs = ""
    for group in groups:
        default_vol = "0.0f" if group == "Master" else "-5.0f"
        group_configs += f"""
            // Configure {group} group
            if (mixer.FindMatchingGroups("{group}").Length > 0)
            {{
                mixer.SetFloat("{group}Volume", {default_vol});
                Debug.Log("[VeilBreakers] Configured mixer group: {group}");
            }}
            else
            {{
                Debug.LogWarning("[VeilBreakers] Mixer group not found: {group}. " +
                    "Please add a group named '{group}' to the AudioMixer.");
            }}"""

    group_list_str = ", ".join(f'"{g}"' for g in groups)

    return f'''// VeilBreakers Auto-Generated: Audio Mixer Setup
// Configures Unity AudioMixer with standard game audio groups
using UnityEngine;
using UnityEditor;
using UnityEngine.Audio;

public static class VeilBreakers_AudioMixerSetup
{{
    private static readonly string MixerPath = "Assets/Audio/VeilBreakersMixer.mixer";
    private static readonly string[] RequiredGroups = new string[] {{ {group_list_str} }};

    [MenuItem("VeilBreakers/Audio/Setup Audio Mixer")]
    public static void Execute()
    {{
        // Load the template mixer asset
        AudioMixer mixer = AssetDatabase.LoadAssetAtPath<AudioMixer>(MixerPath);

        if (mixer == null)
        {{
            Debug.LogError("[VeilBreakers] AudioMixer not found at: " + MixerPath +
                "\\nPlease create an AudioMixer at this path first, then run this setup again." +
                "\\nRequired groups: {", ".join(groups)}");

            // Create a helpful README at the mixer location
            string dir = System.IO.Path.GetDirectoryName(MixerPath);
            if (!string.IsNullOrEmpty(dir) && !System.IO.Directory.Exists(dir))
            {{
                System.IO.Directory.CreateDirectory(dir);
            }}

            string readme = "Create an AudioMixer here named VeilBreakersMixer.\\n" +
                "Add these groups: {", ".join(groups)}\\n" +
                "Then run VeilBreakers > Audio > Setup Audio Mixer.";
            System.IO.File.WriteAllText(
                System.IO.Path.Combine(dir ?? "Assets/Audio", "README_Mixer_Setup.txt"),
                readme
            );
            AssetDatabase.Refresh();
            return;
        }}

        Debug.Log("[VeilBreakers] Configuring AudioMixer: " + MixerPath);
{group_configs}

        Debug.Log("[VeilBreakers] AudioMixer setup complete. Groups configured: " +
            string.Join(", ", RequiredGroups));
    }}
}}
'''


def generate_audio_pool_manager_script(
    pool_size: int = 16,
    max_sources: int = 32,
) -> str:
    """Generate C# audio pool manager with priority and ducking.

    Creates a MonoBehaviour that manages a pool of AudioSources with
    priority-based recycling and volume ducking support.

    Args:
        pool_size: Initial number of AudioSources in the pool.
        max_sources: Maximum number of AudioSources allowed.

    Returns:
        Complete C# source string.
    """
    return f'''// VeilBreakers Auto-Generated: Audio Pool Manager
// Object pooling for AudioSources with priority system and ducking
using UnityEngine;
using System.Collections.Generic;
using System.Linq;

/// <summary>
/// Audio pool manager with configurable pooling, priority system, and ducking.
/// Attach to a persistent GameObject (e.g., AudioManager).
/// </summary>
public class VeilBreakers_AudioPoolManager : MonoBehaviour
{{
    [Header("Pool Configuration")]
    [SerializeField] private int poolSize = {pool_size};
    [SerializeField] private int maxSources = {max_sources};

    [Header("Ducking")]
    [SerializeField] private float duckVolume = 0.2f;
    [SerializeField] private float duckFadeDuration = 0.3f;

    private List<AudioSource> _pool = new List<AudioSource>();
    private Dictionary<AudioSource, float> _priorities = new Dictionary<AudioSource, float>();
    private Dictionary<AudioSource, float> _originalVolumes = new Dictionary<AudioSource, float>();
    private bool _isDucking = false;

    private static VeilBreakers_AudioPoolManager _instance;
    public static VeilBreakers_AudioPoolManager Instance => _instance;

    private void Awake()
    {{
        if (_instance != null && _instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        _instance = this;
        DontDestroyOnLoad(gameObject);

        InitializePool();
    }}

    private void InitializePool()
    {{
        for (int i = 0; i < poolSize; i++)
        {{
            CreatePooledSource();
        }}
    }}

    private AudioSource CreatePooledSource()
    {{
        GameObject child = new GameObject("VB_PooledAudio_" + _pool.Count);
        child.transform.SetParent(transform);
        AudioSource source = child.AddComponent<AudioSource>();
        source.playOnAwake = false;
        source.spatialBlend = 1.0f;
        _pool.Add(source);
        _priorities[source] = 0f;
        return source;
    }}

    /// <summary>
    /// Play an AudioClip at a world position with the given priority.
    /// Higher priority sounds replace lower priority ones when the pool is full.
    /// </summary>
    /// <param name="clip">The AudioClip to play.</param>
    /// <param name="position">World position for 3D spatialization.</param>
    /// <param name="priority">Priority value (higher = more important, less likely to be recycled).</param>
    /// <param name="volume">Playback volume (0-1).</param>
    /// <returns>The AudioSource playing the clip, or null if no source available.</returns>
    public AudioSource Play(AudioClip clip, Vector3 position, float priority = 0.5f, float volume = 1.0f)
    {{
        if (clip == null) return null;

        AudioSource source = GetAvailableSource(priority);
        if (source == null) return null;

        source.transform.position = position;
        source.clip = clip;
        source.volume = _isDucking && priority < 0.9f ? volume * duckVolume : volume;
        source.priority = Mathf.RoundToInt((1f - priority) * 256);
        source.Play();

        _priorities[source] = priority;
        _originalVolumes[source] = volume;

        return source;
    }}

    private AudioSource GetAvailableSource(float requestedPriority)
    {{
        // First, try to find an inactive source
        foreach (var source in _pool)
        {{
            if (!source.isPlaying)
                return source;
        }}

        // If pool isn't at max, create a new source
        if (_pool.Count < maxSources)
        {{
            return CreatePooledSource();
        }}

        // Recycle the lowest priority source
        AudioSource lowest = _pool
            .OrderBy(s => _priorities.GetValueOrDefault(s, 0f))
            .First();

        if (_priorities.GetValueOrDefault(lowest, 0f) < requestedPriority)
        {{
            lowest.Stop();
            return lowest;
        }}

        return null; // All sources are higher priority
    }}

    /// <summary>
    /// Enable volume ducking -- lowers all non-critical audio sources.
    /// Useful when playing important dialogue or cinematics.
    /// </summary>
    public void StartDuck()
    {{
        _isDucking = true;
        foreach (var source in _pool)
        {{
            if (source.isPlaying && _priorities.GetValueOrDefault(source, 0f) < 0.9f)
            {{
                source.volume *= duckVolume;
            }}
        }}
    }}

    /// <summary>
    /// Disable volume ducking -- restores original volumes.
    /// </summary>
    public void StopDuck()
    {{
        _isDucking = false;
        foreach (var source in _pool)
        {{
            if (source.isPlaying && _originalVolumes.ContainsKey(source))
            {{
                source.volume = _originalVolumes[source];
            }}
        }}
    }}

    /// <summary>
    /// Returns the number of currently active (playing) sources in the pool.
    /// </summary>
    public int ActiveSourceCount
    {{
        get {{ return _pool.Count(s => s.isPlaying); }}
    }}

    /// <summary>
    /// Returns the total pool size.
    /// </summary>
    public int TotalPoolSize
    {{
        get {{ return _pool.Count; }}
    }}
}}
'''


def generate_animation_event_sfx_script(
    events: list[dict] | None = None,
) -> str:
    """Generate C# editor script that binds SFX to animation keyframes.

    Creates an editor command that uses AnimationUtility.SetAnimationEvents()
    to assign sound effect functions at specified animation frames.

    Args:
        events: List of event dicts, each with:
            - frame (int): Keyframe number
            - function_name (str): Method name to call
            - clip_path (str): Path to AudioClip asset
            Defaults to example footstep events.

    Returns:
        Complete C# source string.
    """
    if events is None:
        events = [
            {"frame": 8, "function_name": "PlayLeftFoot", "clip_path": "Audio/SFX/footstep_left.wav"},
            {"frame": 20, "function_name": "PlayRightFoot", "clip_path": "Audio/SFX/footstep_right.wav"},
        ]

    event_code = ""
    for i, evt in enumerate(events):
        frame = evt.get("frame", 0)
        func_name = evt.get("function_name", f"PlaySFX_{i}")
        clip_path = evt.get("clip_path", "")
        event_code += f"""
            // Event {i}: {func_name} at frame {frame}
            AnimationEvent evt{i} = new AnimationEvent();
            evt{i}.time = {frame}f / clip.frameRate;
            evt{i}.functionName = "{func_name}";
            evt{i}.stringParameter = "{clip_path}";
            eventList.Add(evt{i});
"""

    return f'''// VeilBreakers Auto-Generated: Animation Event SFX Binding
// Assigns SFX function calls to animation keyframes via AnimationUtility
using UnityEngine;
using UnityEditor;
using System.Collections.Generic;

public static class VeilBreakers_AnimationEventSFX
{{
    [MenuItem("VeilBreakers/Audio/Assign Animation SFX Events")]
    public static void Execute()
    {{
        // Get the selected animation clip from the Project window
        AnimationClip clip = Selection.activeObject as AnimationClip;

        if (clip == null)
        {{
            Debug.LogError("[VeilBreakers] No AnimationClip selected. " +
                "Select an AnimationClip in the Project window, then run this command.");
            return;
        }}

        Debug.Log("[VeilBreakers] Assigning SFX events to: " + clip.name);

        List<AnimationEvent> eventList = new List<AnimationEvent>();
{event_code}
        // Apply events to the animation clip
        AnimationUtility.SetAnimationEvents(clip, eventList.ToArray());

        EditorUtility.SetDirty(clip);
        AssetDatabase.SaveAssets();

        Debug.Log("[VeilBreakers] Assigned " + eventList.Count +
            " SFX events to animation clip: " + clip.name);
    }}
}}
'''


def generate_material_impact_audio_script(
    materials: list[str] | None = None,
    pool_size: int = 8,
    cooldown: float = 0.05,
) -> str:
    """Generate physics material-aware impact sound system.

    Creates ``VB_MaterialImpactAudio`` MonoBehaviour that maps
    PhysicMaterial names to AudioClip arrays and plays impact sounds
    based on collision velocity with volume/pitch scaling, per-material
    reverb contribution, weapon-type awareness, AudioSource pooling,
    and per-collider-pair cooldown to prevent rapid-fire spam.

    Args:
        materials: List of surface material names. Defaults to
                   10 dark fantasy standard materials.
        pool_size: Number of pooled AudioSources.
        cooldown: Minimum seconds between impacts on the same collider pair.

    Returns:
        Complete C# source string.
    """
    if materials is None:
        materials = [
            "Stone", "Metal", "Wood", "Flesh", "Dirt",
            "Water", "Chain", "Bone", "Ice", "Cloth",
        ]

    # Build enum entries
    enum_entries = ",\n        ".join(materials)

    # Build serialized fields for material clip arrays
    material_fields = ""
    for mat in materials:
        safe = sanitize_cs_identifier(mat)
        material_fields += f"""
        [Header("{safe}")]
        public AudioClip[] {safe.lower()}Clips;
        [Range(0f, 1f)] public float {safe.lower()}ReverbMix = """
        # Metals/chains echo more, cloth/flesh echo less
        if mat in ("Metal", "Chain"):
            material_fields += "0.7f;"
        elif mat in ("Stone", "Bone", "Ice"):
            material_fields += "0.5f;"
        elif mat in ("Wood",):
            material_fields += "0.3f;"
        elif mat in ("Water",):
            material_fields += "0.4f;"
        else:
            material_fields += "0.15f;"

    # Build switch cases for material detection
    material_cases = ""
    for mat in materials:
        safe = sanitize_cs_identifier(mat)
        material_cases += f"""
                case ImpactMaterial.{safe}:
                    clips = _soundBank.{safe.lower()}Clips;
                    reverbMix = _soundBank.{safe.lower()}ReverbMix;
                    break;"""

    # Build material detection if-chain
    detection_lines = ""
    for i, mat in enumerate(materials):
        safe = sanitize_cs_identifier(mat)
        kw = "if" if i == 0 else "else if"
        detection_lines += f"""
            {kw} (matName.Contains("{mat.lower()}"))
                return ImpactMaterial.{safe};"""

    return f'''// VeilBreakers Auto-Generated: Material Impact Audio System
// Physics material-aware impact sounds with velocity scaling and AudioSource pooling
using UnityEngine;
using System.Collections.Generic;

/// <summary>Impact surface material types.</summary>
public enum ImpactMaterial
{{
    {enum_entries}
}}

/// <summary>Weapon damage type for specialized impact sounds.</summary>
public enum WeaponDamageType
{{
    Blunt,
    Slash,
    Pierce,
    Magic
}}

/// <summary>
/// ScriptableObject containing impact AudioClip arrays per material.
/// Create via Assets > Create > VeilBreakers > Audio > Impact Sound Bank.
/// </summary>
[CreateAssetMenu(fileName = "ImpactSoundBank", menuName = "VeilBreakers/Audio/Impact Sound Bank")]
public class VB_ImpactSoundBank : ScriptableObject
{{{material_fields}

    [Header("Weapon Overrides")]
    public AudioClip[] slashOnFleshClips;
    public AudioClip[] slashOnMetalClips;
    public AudioClip[] bluntOnStoneClips;
}}

/// <summary>
/// Physics material-aware impact sound system.
/// Attach to objects that collide. Maps PhysicMaterial names to sound banks,
/// scales volume/pitch by impact velocity, pools AudioSources, and prevents
/// rapid-fire sound spam via per-collider-pair cooldown.
/// Generated by VeilBreakers MCP toolkit.
/// </summary>
public class VB_MaterialImpactAudio : MonoBehaviour
{{
    [Header("Sound Bank")]
    [SerializeField] private VB_ImpactSoundBank _soundBank;

    [Header("Velocity Mapping")]
    [SerializeField] private float _minVelocity = 0.5f;
    [SerializeField] private float _maxVelocity = 15f;
    [SerializeField] private float _minVolume = 0.1f;
    [SerializeField] private float _maxVolume = 1f;
    [SerializeField] private float _basePitch = 0.95f;
    [SerializeField] private float _maxPitchBoost = 0.15f;
    [SerializeField] private float _pitchRandomRange = 0.08f;

    [Header("Pooling")]
    [SerializeField] private int _poolSize = {pool_size};

    [Header("Cooldown")]
    [SerializeField] private float _cooldownDuration = {cooldown}f;

    [Header("Weapon Type (optional)")]
    [SerializeField] private WeaponDamageType _weaponType = WeaponDamageType.Blunt;
    [SerializeField] private bool _useWeaponOverrides = false;

    [Header("Reverb")]
    [SerializeField] private bool _applyReverbMix = true;

    private List<AudioSource> _audioPool;
    private int _poolIndex;
    private Dictionary<int, float> _cooldownMap = new Dictionary<int, float>();

    private void Awake()
    {{
        InitializePool();
    }}

    private void InitializePool()
    {{
        _audioPool = new List<AudioSource>(_poolSize);
        for (int i = 0; i < _poolSize; i++)
        {{
            GameObject child = new GameObject("VB_ImpactAudio_" + i);
            child.transform.SetParent(transform);
            AudioSource src = child.AddComponent<AudioSource>();
            src.playOnAwake = false;
            src.spatialBlend = 1f;
            src.minDistance = 1f;
            src.maxDistance = 30f;
            src.rolloffMode = AudioRolloffMode.Logarithmic;
            _audioPool.Add(src);
        }}
    }}

    private void OnCollisionEnter(Collision collision)
    {{
        if (_soundBank == null) return;

        // Cooldown check per collider pair
        int pairHash = GetColliderPairHash(collision.collider);
        if (_cooldownMap.TryGetValue(pairHash, out float lastTime))
        {{
            if (Time.time - lastTime < _cooldownDuration)
                return;
        }}
        _cooldownMap[pairHash] = Time.time;

        // Velocity magnitude
        float velocity = collision.relativeVelocity.magnitude;
        if (velocity < _minVelocity) return;

        // Detect material from PhysicMaterial
        ImpactMaterial impactMat = DetectMaterial(collision.collider);

        // Get contact point
        Vector3 contactPoint = collision.contactCount > 0
            ? collision.GetContact(0).point
            : collision.collider.ClosestPoint(transform.position);

        PlayImpact(impactMat, velocity, contactPoint);
    }}

    /// <summary>
    /// Manually trigger an impact sound at a position.
    /// </summary>
    public void PlayImpact(ImpactMaterial material, float velocity, Vector3 position)
    {{
        // Resolve clips
        AudioClip[] clips = null;
        float reverbMix = 0.3f;

        // Check weapon overrides first
        if (_useWeaponOverrides)
        {{
            clips = GetWeaponOverrideClips(material);
        }}

        // Fall back to material clips
        if (clips == null || clips.Length == 0)
        {{
            switch (material)
            {{{material_cases}
                default:
                    clips = _soundBank.{materials[0].lower()}Clips;
                    reverbMix = _soundBank.{materials[0].lower()}ReverbMix;
                    break;
            }}
        }}

        if (clips == null || clips.Length == 0) return;

        // Velocity to volume/pitch
        float velocityNorm = Mathf.InverseLerp(_minVelocity, _maxVelocity, velocity);
        float volume = Mathf.Lerp(_minVolume, _maxVolume, velocityNorm);
        float pitch = _basePitch + (velocityNorm * _maxPitchBoost)
            + Random.Range(-_pitchRandomRange, _pitchRandomRange);

        // Get pooled source
        AudioSource source = GetPooledSource();
        source.transform.position = position;
        source.clip = clips[Random.Range(0, clips.Length)];
        source.volume = volume;
        source.pitch = pitch;

        // Per-material reverb contribution
        if (_applyReverbMix)
        {{
            source.reverbZoneMix = reverbMix;
        }}

        source.Play();
    }}

    private AudioClip[] GetWeaponOverrideClips(ImpactMaterial material)
    {{
        switch (_weaponType)
        {{
            case WeaponDamageType.Slash:
                if (material == ImpactMaterial.Flesh && _soundBank.slashOnFleshClips != null
                    && _soundBank.slashOnFleshClips.Length > 0)
                    return _soundBank.slashOnFleshClips;
                if (material == ImpactMaterial.Metal && _soundBank.slashOnMetalClips != null
                    && _soundBank.slashOnMetalClips.Length > 0)
                    return _soundBank.slashOnMetalClips;
                break;
            case WeaponDamageType.Blunt:
                if (material == ImpactMaterial.Stone && _soundBank.bluntOnStoneClips != null
                    && _soundBank.bluntOnStoneClips.Length > 0)
                    return _soundBank.bluntOnStoneClips;
                break;
        }}
        return null;
    }}

    private ImpactMaterial DetectMaterial(Collider col)
    {{
        if (col.sharedMaterial != null)
        {{
            string matName = col.sharedMaterial.name.ToLower();
{detection_lines}
        }}
        return ImpactMaterial.{materials[0]};
    }}

    private AudioSource GetPooledSource()
    {{
        // Round-robin through pool, prefer non-playing sources
        for (int i = 0; i < _audioPool.Count; i++)
        {{
            int idx = (_poolIndex + i) % _audioPool.Count;
            if (!_audioPool[idx].isPlaying)
            {{
                _poolIndex = (idx + 1) % _audioPool.Count;
                return _audioPool[idx];
            }}
        }}
        // All playing -- recycle oldest
        AudioSource recycled = _audioPool[_poolIndex];
        _poolIndex = (_poolIndex + 1) % _audioPool.Count;
        recycled.Stop();
        return recycled;
    }}

    private int GetColliderPairHash(Collider other)
    {{
        // Combine instance IDs for a unique pair hash
        int a = gameObject.GetInstanceID();
        int b = other.gameObject.GetInstanceID();
        return a < b ? (a * 397) ^ b : (b * 397) ^ a;
    }}

    /// <summary>
    /// Clean up stale cooldown entries periodically.
    /// Call from a manager or invoke on a timer.
    /// </summary>
    public void CleanupCooldowns()
    {{
        List<int> stale = new List<int>();
        foreach (var kvp in _cooldownMap)
        {{
            if (Time.time - kvp.Value > _cooldownDuration * 10f)
                stale.Add(kvp.Key);
        }}
        foreach (int key in stale)
            _cooldownMap.Remove(key);
    }}
}}
'''


def generate_ui_sound_system_script() -> str:
    """Generate C# runtime UI sound manager for dark fantasy menus.

    Creates a singleton MonoBehaviour (VB_UISoundManager) that plays
    UI sounds with per-type AudioClip arrays for variety, pitch
    randomization, per-type cooldown, independent UI volume via mixer
    group, and an AudioSource pool for overlapping sounds.

    Returns:
        Complete C# source string (runtime only, no UnityEditor dependency).
    """
    return '''// VeilBreakers Auto-Generated: UI Sound Manager (AU-01)
// Runtime UI sound infrastructure for dark fantasy menus
using UnityEngine;
using UnityEngine.Audio;
using System.Collections.Generic;

/// <summary>
/// UI sound types covering all common menu interactions.
/// Dark fantasy audio feel: deep clicks, metallic slides, chain rattles.
/// </summary>
public enum UISoundType
{
    ButtonHover,
    ButtonClick,
    ButtonBack,
    TabSwitch,
    SliderChange,
    ToggleOn,
    ToggleOff,
    InventoryOpen,
    InventoryClose,
    ItemPickup,
    ItemDrop,
    ItemEquip,
    ItemUnequip,
    ItemSell,
    ItemBuy,
    SkillUnlock,
    QuestAccept,
    QuestComplete,
    NotificationPopup,
    MenuOpen,
    MenuClose,
    MapOpen,
    MapClose,
    LevelUp,
    Error,
    Confirm,
    Cancel
}

/// <summary>
/// Serializable mapping from a UISoundType to an array of AudioClips.
/// Multiple clips per type enables random variety on each play.
/// </summary>
[System.Serializable]
public class UISoundEntry
{
    public UISoundType soundType;
    [Tooltip("Multiple clips for random variety per play")]
    public AudioClip[] clips;
    [Range(0f, 1f)]
    [Tooltip("Volume multiplier for this sound type")]
    public float volumeScale = 1.0f;
    [Tooltip("Minimum pitch (default 0.95 for subtle variation)")]
    public float minPitch = 0.95f;
    [Tooltip("Maximum pitch (default 1.05 for subtle variation)")]
    public float maxPitch = 1.05f;
    [Tooltip("Cooldown in seconds to prevent spam")]
    public float cooldown = 0.05f;
}

/// <summary>
/// Singleton UI sound manager with DontDestroyOnLoad.
/// Plays UI sounds with per-type clip arrays, pitch randomization,
/// per-type cooldown, independent volume via AudioMixerGroup, and
/// an AudioSource pool for overlapping sounds.
///
/// Usage:
///   VB_UISoundManager.Instance.PlayUISound(UISoundType.ButtonClick);
///
/// Generated by VeilBreakers MCP toolkit.
/// </summary>
public class VB_UISoundManager : MonoBehaviour
{
    [Header("Sound Configuration")]
    [Tooltip("Map each UISoundType to one or more AudioClips")]
    [SerializeField] private UISoundEntry[] soundEntries;

    [Header("Audio Mixer")]
    [Tooltip("Assign the UI mixer group for independent volume control")]
    [SerializeField] private AudioMixerGroup uiMixerGroup;

    [Header("Pool Settings")]
    [Tooltip("Number of AudioSources for overlapping UI sounds")]
    [SerializeField] private int poolSize = 3;

    [Header("Global Settings")]
    [Range(0f, 1f)]
    [SerializeField] private float masterUIVolume = 1.0f;

    private static VB_UISoundManager _instance;
    public static VB_UISoundManager Instance => _instance;

    private AudioSource[] _sourcePool;
    private int _nextSourceIndex;
    private Dictionary<UISoundType, UISoundEntry> _soundMap;
    private Dictionary<UISoundType, float> _lastPlayTime;

    private void Awake()
    {
        if (_instance != null && _instance != this)
        {
            Destroy(gameObject);
            return;
        }
        _instance = this;
        DontDestroyOnLoad(gameObject);

        InitializePool();
        BuildSoundMap();
    }

    private void InitializePool()
    {
        _sourcePool = new AudioSource[poolSize];
        for (int i = 0; i < poolSize; i++)
        {
            GameObject child = new GameObject("VB_UIAudio_" + i);
            child.transform.SetParent(transform);
            AudioSource src = child.AddComponent<AudioSource>();
            src.playOnAwake = false;
            src.spatialBlend = 0.0f; // 2D for UI
            src.loop = false;
            if (uiMixerGroup != null)
                src.outputAudioMixerGroup = uiMixerGroup;
            _sourcePool[i] = src;
        }
        _nextSourceIndex = 0;
    }

    private void BuildSoundMap()
    {
        _soundMap = new Dictionary<UISoundType, UISoundEntry>();
        _lastPlayTime = new Dictionary<UISoundType, float>();

        if (soundEntries == null) return;

        foreach (UISoundEntry entry in soundEntries)
        {
            _soundMap[entry.soundType] = entry;
            _lastPlayTime[entry.soundType] = -999f;
        }
    }

    /// <summary>
    /// Play a UI sound by type. Selects a random clip from the configured
    /// array, applies pitch variation, respects cooldown, and uses the
    /// next available pooled AudioSource.
    /// </summary>
    /// <param name="type">The UI sound type to play.</param>
    public void PlayUISound(UISoundType type)
    {
        if (_soundMap == null || !_soundMap.ContainsKey(type))
            return;

        UISoundEntry entry = _soundMap[type];

        if (entry.clips == null || entry.clips.Length == 0)
            return;

        // Cooldown check
        if (_lastPlayTime.ContainsKey(type))
        {
            if (Time.unscaledTime - _lastPlayTime[type] < entry.cooldown)
                return;
        }
        _lastPlayTime[type] = Time.unscaledTime;

        // Select random clip for variety
        AudioClip clip = entry.clips[Random.Range(0, entry.clips.Length)];
        if (clip == null) return;

        // Get next pooled source (round-robin)
        AudioSource source = GetNextSource();

        // Apply settings
        source.clip = clip;
        source.volume = masterUIVolume * entry.volumeScale;
        source.pitch = Random.Range(entry.minPitch, entry.maxPitch);

        // Ensure mixer group is assigned
        if (uiMixerGroup != null)
            source.outputAudioMixerGroup = uiMixerGroup;

        source.Play();
    }

    /// <summary>
    /// Play a UI sound with a specific volume override.
    /// </summary>
    /// <param name="type">The UI sound type to play.</param>
    /// <param name="volumeOverride">Volume override (0-1), multiplied by masterUIVolume.</param>
    public void PlayUISound(UISoundType type, float volumeOverride)
    {
        if (_soundMap == null || !_soundMap.ContainsKey(type))
            return;

        UISoundEntry entry = _soundMap[type];

        if (entry.clips == null || entry.clips.Length == 0)
            return;

        // Cooldown check
        if (_lastPlayTime.ContainsKey(type))
        {
            if (Time.unscaledTime - _lastPlayTime[type] < entry.cooldown)
                return;
        }
        _lastPlayTime[type] = Time.unscaledTime;

        AudioClip clip = entry.clips[Random.Range(0, entry.clips.Length)];
        if (clip == null) return;

        AudioSource source = GetNextSource();
        source.clip = clip;
        source.volume = masterUIVolume * volumeOverride;
        source.pitch = Random.Range(entry.minPitch, entry.maxPitch);

        if (uiMixerGroup != null)
            source.outputAudioMixerGroup = uiMixerGroup;

        source.Play();
    }

    /// <summary>
    /// Set the master UI volume (0-1). Independent from SFX volume.
    /// </summary>
    public void SetMasterUIVolume(float volume)
    {
        masterUIVolume = Mathf.Clamp01(volume);
    }

    /// <summary>
    /// Get the current master UI volume.
    /// </summary>
    public float GetMasterUIVolume()
    {
        return masterUIVolume;
    }

    /// <summary>
    /// Update the mixer group at runtime (e.g., after loading AudioMixer).
    /// </summary>
    public void SetMixerGroup(AudioMixerGroup group)
    {
        uiMixerGroup = group;
        if (_sourcePool != null)
        {
            foreach (AudioSource src in _sourcePool)
            {
                if (src != null)
                    src.outputAudioMixerGroup = group;
            }
        }
    }

    /// <summary>
    /// Returns whether a specific sound type has been configured with clips.
    /// </summary>
    public bool HasSound(UISoundType type)
    {
        if (_soundMap == null) return false;
        if (!_soundMap.ContainsKey(type)) return false;
        UISoundEntry entry = _soundMap[type];
        return entry.clips != null && entry.clips.Length > 0;
    }

    /// <summary>
    /// Returns the number of configured sound types.
    /// </summary>
    public int ConfiguredSoundCount
    {
        get { return _soundMap != null ? _soundMap.Count : 0; }
    }

    private AudioSource GetNextSource()
    {
        // Prefer non-playing source first
        for (int i = 0; i < _sourcePool.Length; i++)
        {
            int idx = (_nextSourceIndex + i) % _sourcePool.Length;
            if (!_sourcePool[idx].isPlaying)
            {
                _nextSourceIndex = (idx + 1) % _sourcePool.Length;
                return _sourcePool[idx];
            }
        }
        // All playing -- round-robin recycle
        AudioSource recycled = _sourcePool[_nextSourceIndex];
        _nextSourceIndex = (_nextSourceIndex + 1) % _sourcePool.Length;
        recycled.Stop();
        return recycled;
    }
}
'''
