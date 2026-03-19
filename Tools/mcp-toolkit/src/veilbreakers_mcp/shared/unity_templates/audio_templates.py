"""C# audio template generators for Unity audio system setup.

Each function returns a complete C# source string that can be written to
a Unity project. Editor scripts go to Assets/Editor/Generated/Audio/ and
register as MenuItem commands under "VeilBreakers/Audio/...". Runtime
scripts go to Assets/Scripts/Runtime/Audio/.

All generated scripts are marked with VeilBreakers namespace comments
for identification.
"""

from __future__ import annotations


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
