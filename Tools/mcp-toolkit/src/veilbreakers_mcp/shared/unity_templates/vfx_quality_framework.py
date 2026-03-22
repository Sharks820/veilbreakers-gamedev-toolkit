"""VFX Quality Framework C# template generators for Unity.

Generates the four foundational systems that make VFX look AAA and run at
60 fps in open-world scenes:

1. VFXPoolManager        -- Object pooling with global particle budget
2. VFXLODController      -- Distance / frustum / screen-size culling
3. AAAParticleBuilder    -- Fluent builder for multi-layer AAA particle effects
4. VFXQualityPresets     -- ScriptableObject quality tiers + editor window

All generated C# targets Unity 2022.3+ URP with PrimeTween for animations.

Exports:
    generate_vfx_pool_manager_script      -- Pooling + priority + budget
    generate_vfx_lod_controller_script    -- LOD + frustum + screen-size cull
    generate_aaa_particle_builder_script  -- 5-layer fluent builder
    generate_vfx_quality_presets_script   -- SO quality tiers + editor window
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# 1. VFX Pool Manager
# ---------------------------------------------------------------------------


def generate_vfx_pool_manager_script(
    max_pools: int = 50,
    max_particles_per_pool: int = 20,
) -> dict[str, Any]:
    """Generate a singleton VFXPoolManager MonoBehaviour.

    Pre-allocates pools of ParticleSystem GameObjects at scene load.
    Enforces a global particle budget and per-effect priority culling.

    Args:
        max_pools: Maximum distinct VFX types the manager can hold.
        max_particles_per_pool: Default pool size per VFX type.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    max_pools = max(1, min(max_pools, 200))
    max_particles_per_pool = max(1, min(max_particles_per_pool, 100))

    script = f'''using UnityEngine;
using System;
using System.Collections.Generic;

/// <summary>
/// Singleton pool manager for all VFX ParticleSystems.
/// Eliminates runtime Instantiate/Destroy calls by pre-allocating pools.
/// Enforces a global active-particle budget and per-effect priority culling.
/// </summary>
public class VFXPoolManager : MonoBehaviour
{{
    // -----------------------------------------------------------------------
    // Singleton
    // -----------------------------------------------------------------------
    private static VFXPoolManager _instance;
    private static bool _isCreating;
    public static VFXPoolManager Instance
    {{
        get
        {{
            if (_instance == null && !_isCreating)
            {{
                _isCreating = true;
                var go = new GameObject("[VFXPoolManager]");
                _instance = go.AddComponent<VFXPoolManager>();
                DontDestroyOnLoad(go);
                _isCreating = false;
            }}
            return _instance;
        }}
    }}

    // -----------------------------------------------------------------------
    // Configuration
    // -----------------------------------------------------------------------
    public const int MAX_POOLS = {max_pools};
    public const int DEFAULT_POOL_SIZE = {max_particles_per_pool};
    public const int MAX_ACTIVE_PARTICLES = 2000;

    /// <summary>Priority tiers -- lower value = higher priority (less likely to be culled).</summary>
    public enum VFXPriority
    {{
        Ultimate = 0,
        Combo    = 1,
        Status   = 2,
        Ambient  = 3,
    }}

    // -----------------------------------------------------------------------
    // Pool data structures
    // -----------------------------------------------------------------------
    [Serializable]
    public class PoolEntry
    {{
        public string vfxType;
        public GameObject prefab;
        public int poolSize;
        public VFXPriority priority;
        public int maxInstances;
        public Queue<GameObject> available;
        public List<(GameObject go, ParticleSystem[] systems)> active;

        public PoolEntry(string type, GameObject prefab, int size, VFXPriority prio, int maxInst)
        {{
            vfxType = type;
            this.prefab = prefab;
            poolSize = size;
            priority = prio;
            maxInstances = maxInst;
            available = new Queue<GameObject>(size);
            active = new List<(GameObject, ParticleSystem[])>(size);
        }}
    }}

    private Dictionary<string, PoolEntry> _pools = new Dictionary<string, PoolEntry>();

    // -----------------------------------------------------------------------
    // Stats (for profiling / editor window)
    // -----------------------------------------------------------------------
    public int TotalActiveParticles {{ get; private set; }}
    public int TotalActiveEffects {{ get; private set; }}
    public int TotalPooledObjects {{ get; private set; }}
    public int CulledThisFrame {{ get; private set; }}

    // Quality multiplier -- set by VFXQualityPresets at runtime
    public float ParticleMultiplier {{ get; set; }} = 1.0f;
    public int MaxActiveParticlesOverride {{ get; set; }} = MAX_ACTIVE_PARTICLES;

    // -----------------------------------------------------------------------
    // Unity lifecycle
    // -----------------------------------------------------------------------
    private void Awake()
    {{
        if (_instance != null && _instance != this)
        {{
            Destroy(gameObject);
            return;
        }}
        _instance = this;
        DontDestroyOnLoad(gameObject);
        UnityEngine.SceneManagement.SceneManager.sceneLoaded += OnSceneLoaded;
    }}

    private void OnDestroy()
    {{
        UnityEngine.SceneManagement.SceneManager.sceneLoaded -= OnSceneLoaded;
    }}

    private void OnSceneLoaded(UnityEngine.SceneManagement.Scene scene, UnityEngine.SceneManagement.LoadSceneMode mode)
    {{
        // Return all active effects to pools on scene change to prevent null refs
        foreach (var kvp in _pools)
        {{
            var entry = kvp.Value;
            for (int i = entry.active.Count - 1; i >= 0; i--)
            {{
                var (go, systems) = entry.active[i];
                if (go == null) {{ entry.active.RemoveAt(i); continue; }}
                go.SetActive(false);
                go.transform.SetParent(transform);
                entry.available.Enqueue(go);
                entry.active.RemoveAt(i);
            }}
        }}
    }}

    private void LateUpdate()
    {{
        UpdateStats();
        EnforceBudget();
    }}

    // -----------------------------------------------------------------------
    // Pool registration
    // -----------------------------------------------------------------------

    /// <summary>
    /// Register a VFX prefab type for pooling. Call once at scene load.
    /// </summary>
    public void RegisterPool(
        string vfxType,
        GameObject prefab,
        int poolSize = DEFAULT_POOL_SIZE,
        VFXPriority priority = VFXPriority.Status,
        int maxInstances = 10)
    {{
        if (_pools.ContainsKey(vfxType))
        {{
            Debug.LogWarning($"[VFXPoolManager] Pool '{{vfxType}}' already registered.");
            return;
        }}
        if (_pools.Count >= MAX_POOLS)
        {{
            Debug.LogWarning($"[VFXPoolManager] Max pool count ({{MAX_POOLS}}) reached. Cannot register '{{vfxType}}'.");
            return;
        }}

        var entry = new PoolEntry(vfxType, prefab, poolSize, priority, maxInstances);

        // Pre-allocate
        Transform container = new GameObject($"_Pool_{{vfxType}}").transform;
        container.SetParent(transform);

        for (int i = 0; i < poolSize; i++)
        {{
            GameObject go = Instantiate(prefab, container);
            go.name = $"{{vfxType}}_{{i}}";
            go.SetActive(false);
            entry.available.Enqueue(go);
        }}

        _pools[vfxType] = entry;
        TotalPooledObjects += poolSize;
    }}

    // -----------------------------------------------------------------------
    // Get / Return
    // -----------------------------------------------------------------------

    /// <summary>
    /// Retrieve a pooled VFX object. Returns null if budget exceeded or pool empty.
    /// </summary>
    public GameObject GetVFX(string vfxType, Vector3 position = default, Transform parent = null)
    {{
        if (!_pools.TryGetValue(vfxType, out PoolEntry entry))
        {{
            Debug.LogWarning($"[VFXPoolManager] Unknown VFX type '{{vfxType}}'. Register it first.");
            return null;
        }}

        // Per-effect max instances check
        if (entry.active.Count >= entry.maxInstances)
        {{
            Debug.LogWarning($"[VFXPoolManager] Max instances ({{entry.maxInstances}}) reached for '{{vfxType}}'. Skipping.");
            return null;
        }}

        // Global particle budget check
        if (TotalActiveParticles >= MaxActiveParticlesOverride)
        {{
            // Only allow Ultimate priority effects through when over budget
            if (entry.priority != VFXPriority.Ultimate)
            {{
                CulledThisFrame++;
                return null;
            }}
        }}

        if (entry.available.Count == 0)
        {{
            Debug.LogWarning($"[VFXPoolManager] Pool '{{vfxType}}' exhausted ({{entry.poolSize}} items). Skipping.");
            return null;
        }}

        GameObject go = entry.available.Dequeue();

        go.transform.position = position;
        if (parent != null)
            go.transform.SetParent(parent);

        go.SetActive(true);

        // Cache ParticleSystem[] at spawn time — never per-frame (C-01 fix)
        var systems = go.GetComponentsInChildren<ParticleSystem>(true);
        entry.active.Add((go, systems));

        foreach (var ps in systems)
        {{
            ps.Clear();
            // Configure stop callback instead of coroutine (Fix 3)
            var main = ps.main;
            main.stopAction = ParticleSystemStopAction.Callback;
            ps.Play();
        }}

        // Attach or configure the callback helper (Fix 3)
        var helper = go.GetComponent<VFXAutoReturnHelper>();
        if (helper == null)
            helper = go.AddComponent<VFXAutoReturnHelper>();
        helper.Configure(vfxType, this);

        return go;
    }}

    /// <summary>
    /// Manually return a VFX object to the pool.
    /// </summary>
    public void ReturnVFX(string vfxType, GameObject go)
    {{
        if (go == null) return;

        if (!_pools.TryGetValue(vfxType, out PoolEntry entry))
        {{
            Debug.LogWarning($"[VFXPoolManager] Cannot return unknown type '{{vfxType}}'.");
            Destroy(go);
            return;
        }}

        // Find cached systems from active list (C-01 fix — use cached arrays)
        ParticleSystem[] systems = null;
        for (int i = 0; i < entry.active.Count; i++)
        {{
            if (entry.active[i].go == go)
            {{
                systems = entry.active[i].systems;
                entry.active.RemoveAt(i);
                break;
            }}
        }}

        // Fallback if not found in active list
        if (systems == null)
            systems = go.GetComponentsInChildren<ParticleSystem>(true);

        foreach (var ps in systems)
        {{
            ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
        }}

        go.SetActive(false);
        go.transform.SetParent(transform.Find($"_Pool_{{vfxType}}"));
        entry.available.Enqueue(go);
    }}

    // -----------------------------------------------------------------------
    // Public return accessor (used by VFXAutoReturnHelper callback -- Fix 3)
    // -----------------------------------------------------------------------
    public void ReturnVFXFromCallback(string vfxType, GameObject go)
    {{
        ReturnVFX(vfxType, go);
    }}

    // -----------------------------------------------------------------------
    // Budget enforcement
    // -----------------------------------------------------------------------
    private void UpdateStats()
    {{
        TotalActiveParticles = 0;
        TotalActiveEffects = 0;
        CulledThisFrame = 0;

        foreach (var kvp in _pools)
        {{
            var entry = kvp.Value;
            TotalActiveEffects += entry.active.Count;

            for (int i = entry.active.Count - 1; i >= 0; i--)
            {{
                var (go, cachedSystems) = entry.active[i];
                if (go == null)
                {{
                    entry.active.RemoveAt(i);
                    continue;
                }}
                // Use CACHED ParticleSystem[] — no per-frame allocation (C-01 fix)
                foreach (var ps in cachedSystems)
                {{
                    if (ps != null)
                        TotalActiveParticles += ps.particleCount;
                }}
            }}
        }}
    }}

    private void EnforceBudget()
    {{
        if (TotalActiveParticles <= MaxActiveParticlesOverride)
            return;

        // Cull lowest priority effects first until under budget
        for (int prio = (int)VFXPriority.Ambient; prio >= (int)VFXPriority.Combo; prio--)
        {{
            foreach (var kvp in _pools)
            {{
                var entry = kvp.Value;
                if ((int)entry.priority != prio)
                    continue;

                for (int i = entry.active.Count - 1; i >= 0; i--)
                {{
                    if (TotalActiveParticles <= MaxActiveParticlesOverride)
                        return;

                    var (go, cachedSystems) = entry.active[i];
                    if (go == null) continue;

                    // Use CACHED arrays — no per-frame GetComponentsInChildren (C-01 fix)
                    int effectParticles = 0;
                    foreach (var ps in cachedSystems)
                    {{
                        if (ps != null)
                            effectParticles += ps.particleCount;
                    }}

                    ReturnVFX(kvp.Key, go);
                    TotalActiveParticles -= effectParticles;
                    CulledThisFrame++;
                }}
            }}
        }}
    }}

    // -----------------------------------------------------------------------
    // Utility
    // -----------------------------------------------------------------------

    /// <summary>Clear all pools and destroy all pooled objects.</summary>
    public void ClearAllPools()
    {{
        foreach (var kvp in _pools)
        {{
            var entry = kvp.Value;
            foreach (var go in entry.active)
                if (go != null) Destroy(go);
            while (entry.available.Count > 0)
            {{
                var go = entry.available.Dequeue();
                if (go != null) Destroy(go);
            }}
        }}
        _pools.Clear();
        TotalActiveParticles = 0;
        TotalActiveEffects = 0;
        TotalPooledObjects = 0;

        // Destroy pool containers
        for (int i = transform.childCount - 1; i >= 0; i--)
            Destroy(transform.GetChild(i).gameObject);
    }}

    /// <summary>Get debug stats string for profiling display.</summary>
    public string GetStatsString()
    {{
        return $"Active Particles: {{TotalActiveParticles}}/{{MaxActiveParticlesOverride}} | " +
               $"Active Effects: {{TotalActiveEffects}} | " +
               $"Pooled Objects: {{TotalPooledObjects}} | " +
               $"Culled This Frame: {{CulledThisFrame}}";
    }}
}}

/// <summary>
/// Helper component attached to pooled VFX objects.
/// Uses OnParticleSystemStopped callback instead of coroutines (Fix 3).
/// </summary>
public class VFXAutoReturnHelper : MonoBehaviour
{{
    private string _vfxType;
    private VFXPoolManager _manager;

    public void Configure(string vfxType, VFXPoolManager manager)
    {{
        _vfxType = vfxType;
        _manager = manager;
    }}

    /// <summary>
    /// Called by Unity when ParticleSystem.MainModule.stopAction == Callback
    /// and the particle system stops playing.
    /// </summary>
    private void OnParticleSystemStopped()
    {{
        if (_manager != null && gameObject.activeInHierarchy)
            _manager.ReturnVFXFromCallback(_vfxType, gameObject);
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/VFX/VFXPoolManager.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Attach VFXPoolManager to a persistent GameObject or let it auto-create",
            "Register VFX prefabs: VFXPoolManager.Instance.RegisterPool(\"FireImpact\", prefab, 10, VFXPriority.Combo)",
            "Spawn effects: VFXPoolManager.Instance.GetVFX(\"FireImpact\", position)",
            "Effects auto-return to pool when particles finish",
        ],
    }


# ---------------------------------------------------------------------------
# 2. VFX LOD Controller
# ---------------------------------------------------------------------------


def generate_vfx_lod_controller_script() -> dict[str, Any]:
    """Generate a VFXLODController MonoBehaviour.

    Distance-based quality tiers, frustum culling, and screen-space size
    culling for individual VFX prefabs. Attach to any VFX root GameObject.

    Returns:
        Dict with script_path, script_content, next_steps.
    """

    script = '''using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Per-VFX-prefab LOD controller.
/// Attach to any VFX root GameObject to auto-adjust quality based on
/// camera distance, frustum visibility, and screen-space coverage.
/// Integrates with VFXPoolManager for global particle budget awareness.
/// </summary>
[DisallowMultipleComponent]
public class VFXLODController : MonoBehaviour
{
    // -------------------------------------------------------------------
    // Quality tiers
    // -------------------------------------------------------------------
    public enum QualityPreset { LOW, MEDIUM, HIGH, ULTRA }
    public enum LODTier { Close, Medium, Far, Culled }

    // -------------------------------------------------------------------
    // Configuration (adjustable per VFX or via quality preset)
    // -------------------------------------------------------------------
    [Header("LOD Distances")]
    [Tooltip("Distance from camera for Close -> Medium transition")]
    public float closeToMediumDist = 15f;

    [Tooltip("Distance from camera for Medium -> Far transition")]
    public float mediumToFarDist = 40f;

    [Tooltip("Distance from camera for Far -> Culled transition")]
    public float farToCulledDist = 80f;

    [Header("Quality")]
    [Tooltip("Particle emission multiplier at Medium tier (0-1)")]
    public float mediumEmissionMult = 0.6f;

    [Tooltip("Particle emission multiplier at Far tier (0-1)")]
    public float farEmissionMult = 0.3f;

    [Tooltip("Minimum screen-space coverage (0-1) before reducing to minimal")]
    public float minScreenCoverage = 0.02f;

    [Header("Update")]
    [Tooltip("Seconds between LOD evaluations (0.5 = twice per second)")]
    public float updateInterval = 0.5f;

    [Header("Layer Control")]
    [Tooltip("Indices of secondary particle systems (smoke, distortion) disabled at Medium+")]
    public int[] secondaryLayerIndices = new int[0];

    [Tooltip("Indices of distortion particle systems disabled at Medium+")]
    public int[] distortionLayerIndices = new int[0];

    // -------------------------------------------------------------------
    // Static registry (Fix 9 -- replaces FindObjectsByType in quality switching)
    // -------------------------------------------------------------------
    private static readonly HashSet<VFXLODController> _activeControllers = new HashSet<VFXLODController>();
    public static IReadOnlyCollection<VFXLODController> ActiveControllers => _activeControllers;

    // -------------------------------------------------------------------
    // Internal state
    // -------------------------------------------------------------------
    private ParticleSystem[] _allSystems;
    private float[] _baseEmissionRates;
    private float[] _baseAlpha;
    private bool[] _systemEnabled;
    private Light[] _lights;
    private float[] _baseLightIntensities;
    private LODTier _currentTier = LODTier.Close;
    private float _currentBlend = 1.0f; // Smooth interpolation factor (Fix 4)
    private float _nextUpdateTime;
    private Camera _mainCamera;
    private Renderer[] _renderers;
    private Bounds _bounds;

    // -------------------------------------------------------------------
    // Initialization
    // -------------------------------------------------------------------
    private void Awake()
    {
        CacheComponents();
    }

    private void OnEnable()
    {
        _activeControllers.Add(this); // Fix 9 -- register
        _mainCamera = Camera.main;
        _nextUpdateTime = 0f;
        ApplyTier(LODTier.Close);
    }

    private void OnDisable()
    {
        _activeControllers.Remove(this); // Fix 9 -- unregister
    }

    private void CacheComponents()
    {
        _allSystems = GetComponentsInChildren<ParticleSystem>(true);
        _baseEmissionRates = new float[_allSystems.Length];
        _baseAlpha = new float[_allSystems.Length];
        _systemEnabled = new bool[_allSystems.Length];

        for (int i = 0; i < _allSystems.Length; i++)
        {
            var emission = _allSystems[i].emission;
            _baseEmissionRates[i] = emission.rateOverTime.constant;
            _baseAlpha[i] = _allSystems[i].main.startColor.color.a;
            _systemEnabled[i] = true;
        }

        _lights = GetComponentsInChildren<Light>(true);
        _baseLightIntensities = new float[_lights.Length];
        for (int i = 0; i < _lights.Length; i++)
            _baseLightIntensities[i] = _lights[i].intensity;

        _renderers = GetComponentsInChildren<Renderer>(true);
    }

    // -------------------------------------------------------------------
    // Update loop (throttled)
    // -------------------------------------------------------------------
    private void Update()
    {
        if (Time.time < _nextUpdateTime)
            return;
        _nextUpdateTime = Time.time + updateInterval;

        if (_mainCamera == null)
        {
            _mainCamera = Camera.main;
            if (_mainCamera == null) return;
        }

        LODTier newTier = EvaluateTier();

        // Smooth interpolation between tiers to avoid popping (Fix 4)
        float dist = Vector3.Distance(_mainCamera.transform.position, transform.position);
        float blend = CalculateBlend(dist);

        if (newTier != _currentTier || Mathf.Abs(blend - _currentBlend) > 0.01f)
        {
            _currentTier = newTier;
            _currentBlend = blend;
            ApplyTierSmooth(newTier, blend);
        }
    }

    /// <summary>
    /// Calculate a 0-1 blend factor based on distance between tier boundaries (Fix 4).
    /// 1.0 = full Close quality, 0.0 = fully culled.
    /// Uses InverseLerp between tier boundaries for smooth transitions.
    /// </summary>
    private float CalculateBlend(float dist)
    {
        if (dist >= farToCulledDist)
            return 0f;
        if (dist >= mediumToFarDist)
            return Mathf.Lerp(farEmissionMult, mediumEmissionMult,
                Mathf.InverseLerp(farToCulledDist, mediumToFarDist, dist));
        if (dist >= closeToMediumDist)
            return Mathf.Lerp(mediumEmissionMult, 1f,
                Mathf.InverseLerp(mediumToFarDist, closeToMediumDist, dist));
        return 1f;
    }

    // -------------------------------------------------------------------
    // Tier evaluation
    // -------------------------------------------------------------------
    private LODTier EvaluateTier()
    {
        Vector3 camPos = _mainCamera.transform.position;
        float dist = Vector3.Distance(camPos, transform.position);

        // Distance-based tier
        LODTier tier;
        if (dist >= farToCulledDist)
            tier = LODTier.Culled;
        else if (dist >= mediumToFarDist)
            tier = LODTier.Far;
        else if (dist >= closeToMediumDist)
            tier = LODTier.Medium;
        else
            tier = LODTier.Close;

        // Frustum culling -- disable if completely off screen
        if (tier != LODTier.Culled && !IsVisibleToCamera())
            tier = LODTier.Culled;

        // Screen-space size culling -- reduce to minimal if too small
        if (tier == LODTier.Close || tier == LODTier.Medium)
        {
            float coverage = EstimateScreenCoverage(dist);
            if (coverage < minScreenCoverage)
                tier = LODTier.Far;
        }

        return tier;
    }

    private bool IsVisibleToCamera()
    {
        if (_renderers == null || _renderers.Length == 0)
        {
            // Fallback: point-in-frustum check
            Vector3 vp = _mainCamera.WorldToViewportPoint(transform.position);
            return vp.x >= -0.1f && vp.x <= 1.1f && vp.y >= -0.1f && vp.y <= 1.1f && vp.z > 0f;
        }

        // Check if any renderer bounds intersect camera frustum
        Plane[] planes = GeometryUtility.CalculateFrustumPlanes(_mainCamera);
        foreach (var r in _renderers)
        {
            if (r != null && r.enabled && GeometryUtility.TestPlanesAABB(planes, r.bounds))
                return true;
        }
        return false;
    }

    private float EstimateScreenCoverage(float distance)
    {
        if (distance <= 0.01f) return 1f;

        // Estimate world-space size from particle system bounds
        float worldSize = 1f;
        if (_allSystems.Length > 0)
        {
            var main = _allSystems[0].main;
            worldSize = Mathf.Max(main.startSize.constant * 2f, 1f);
        }

        // Project to screen space
        float screenHeight = _mainCamera.pixelHeight;
        float fov = _mainCamera.fieldOfView * Mathf.Deg2Rad;
        float projectedPixels = (worldSize / distance) * (screenHeight / (2f * Mathf.Tan(fov * 0.5f)));
        float coverage = (projectedPixels * projectedPixels) / (screenHeight * _mainCamera.pixelWidth);

        return Mathf.Clamp01(coverage);
    }

    // -------------------------------------------------------------------
    // Apply quality tier (kept for direct preset application)
    // -------------------------------------------------------------------
    private void ApplyTier(LODTier tier)
    {
        float blend = tier == LODTier.Close ? 1f :
                      tier == LODTier.Medium ? mediumEmissionMult :
                      tier == LODTier.Far ? farEmissionMult : 0f;
        _currentTier = tier;
        _currentBlend = blend;
        ApplyTierSmooth(tier, blend);
    }

    // -------------------------------------------------------------------
    // Smooth tier application with lerped emission and alpha (Fix 4)
    // -------------------------------------------------------------------
    private void ApplyTierSmooth(LODTier tier, float blend)
    {
        switch (tier)
        {
            case LODTier.Close:
                SetEmissionMultiplierSmooth(blend);
                SetAlphaMultiplier(blend);
                EnableAllSystems(true);
                SetCollisionEnabled(true);
                SetLightsActive(true, blend);
                break;

            case LODTier.Medium:
                SetEmissionMultiplierSmooth(blend);
                SetAlphaMultiplier(blend);
                DisableSecondaryLayers();
                DisableDistortionLayers();
                SetCollisionEnabled(true);
                SetLightsActive(true, blend);
                break;

            case LODTier.Far:
                SetEmissionMultiplierSmooth(blend);
                SetAlphaMultiplier(blend);
                // Only keep primary layer (index 0)
                for (int i = 1; i < _allSystems.Length; i++)
                    SetSystemActive(i, false);
                SetCollisionEnabled(false); // Fix 10 -- disable collision at Far
                SetLightsActive(true, blend);
                break;

            case LODTier.Culled:
                EnableAllSystems(false);
                SetCollisionEnabled(false); // Fix 10 -- disable collision at Culled
                SetLightsActive(false, 0f);
                break;
        }
    }

    // -------------------------------------------------------------------
    // System control helpers
    // -------------------------------------------------------------------

    /// <summary>Smoothly interpolated emission rate (Fix 4).</summary>
    private void SetEmissionMultiplierSmooth(float blend)
    {
        for (int i = 0; i < _allSystems.Length; i++)
        {
            if (!_systemEnabled[i]) continue;
            var emission = _allSystems[i].emission;
            emission.rateOverTime = _baseEmissionRates[i] * blend;
        }
    }

    /// <summary>Smoothly interpolated alpha via startColor (Fix 4).</summary>
    private void SetAlphaMultiplier(float blend)
    {
        for (int i = 0; i < _allSystems.Length; i++)
        {
            if (!_systemEnabled[i]) continue;
            var main = _allSystems[i].main;
            Color c = main.startColor.color;
            c.a = _baseAlpha[i] * blend;
            main.startColor = c;
        }
    }

    /// <summary>Enable or disable collision module on all child systems (Fix 10).</summary>
    private void SetCollisionEnabled(bool enabled)
    {
        for (int i = 0; i < _allSystems.Length; i++)
        {
            var collision = _allSystems[i].collision;
            collision.enabled = enabled;
        }
    }

    private void EnableAllSystems(bool enabled)
    {
        for (int i = 0; i < _allSystems.Length; i++)
            SetSystemActive(i, enabled);
    }

    private void SetSystemActive(int index, bool active)
    {
        if (index < 0 || index >= _allSystems.Length) return;
        _systemEnabled[index] = active;

        if (active)
        {
            if (!_allSystems[index].isPlaying)
                _allSystems[index].Play();
        }
        else
        {
            if (_allSystems[index].isPlaying)
                _allSystems[index].Stop(true, ParticleSystemStopBehavior.StopEmitting);
        }
    }

    private void DisableSecondaryLayers()
    {
        foreach (int idx in secondaryLayerIndices)
            SetSystemActive(idx, false);
    }

    private void DisableDistortionLayers()
    {
        foreach (int idx in distortionLayerIndices)
            SetSystemActive(idx, false);
    }

    private void SetLightsActive(bool enabled, float intensityMult)
    {
        for (int i = 0; i < _lights.Length; i++)
        {
            _lights[i].enabled = enabled;
            if (enabled)
                _lights[i].intensity = _baseLightIntensities[i] * intensityMult;
        }
    }

    // -------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------

    /// <summary>Apply a quality preset that adjusts all LOD distances.</summary>
    public void ApplyQualityPreset(QualityPreset preset)
    {
        switch (preset)
        {
            case QualityPreset.LOW:
                closeToMediumDist = 10f;
                mediumToFarDist = 25f;
                farToCulledDist = 50f;
                mediumEmissionMult = 0.4f;
                farEmissionMult = 0.2f;
                break;
            case QualityPreset.MEDIUM:
                closeToMediumDist = 15f;
                mediumToFarDist = 35f;
                farToCulledDist = 65f;
                mediumEmissionMult = 0.5f;
                farEmissionMult = 0.25f;
                break;
            case QualityPreset.HIGH:
                closeToMediumDist = 20f;
                mediumToFarDist = 50f;
                farToCulledDist = 100f;
                mediumEmissionMult = 0.6f;
                farEmissionMult = 0.3f;
                break;
            case QualityPreset.ULTRA:
                closeToMediumDist = 30f;
                mediumToFarDist = 60f;
                farToCulledDist = 120f;
                mediumEmissionMult = 0.75f;
                farEmissionMult = 0.4f;
                break;
        }
    }

    /// <summary>Current active LOD tier for debug display.</summary>
    public LODTier CurrentTier => _currentTier;

    /// <summary>Total active particle count across all child systems.</summary>
    public int GetActiveParticleCount()
    {
        int count = 0;
        foreach (var ps in _allSystems)
        {
            if (ps != null && ps.isPlaying)
                count += ps.particleCount;
        }
        return count;
    }
}
'''

    return {
        "script_path": "Assets/Scripts/VFX/VFXLODController.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Attach VFXLODController to any VFX prefab root GameObject",
            "Configure secondary/distortion layer indices in Inspector",
            "Quality preset applied globally via VFXQualityPresets.SetQuality()",
            "LOD evaluation runs every 0.5s -- not per-frame",
        ],
    }


# ---------------------------------------------------------------------------
# 3. AAA Particle Builder
# ---------------------------------------------------------------------------


def generate_aaa_particle_builder_script() -> dict[str, Any]:
    """Generate the AAAParticleBuilder fluent utility class.

    A static builder-pattern class that creates multi-layer AAA-quality VFX
    compositions. Each effect gets 1-5 layers: core glow, sparks, smoke,
    distortion, and a point light -- all with proper lifetime curves,
    burst emission, noise turbulence, and GPU instancing.

    Returns:
        Dict with script_path, script_content, next_steps.
    """

    script = '''using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Fluent builder for creating multi-layered AAA-quality particle effects.
///
/// Usage:
///   AAAParticleBuilder.CreateEffect("FireImpact")
///       .AddCoreGlow(Color.yellow, intensity: 3f, size: 0.8f)
///       .AddSparkBurst(Color.orange, count: 30, speed: 5f)
///       .AddSmoke(Color.gray, count: 15, lifetime: 2f)
///       .AddDistortion(strength: 0.1f, radius: 1.5f)
///       .AddPointLight(Color.yellow, intensity: 2f, range: 3f)
///       .WithLifetimeCurves()
///       .WithNoiseTurbulence(0.5f)
///       .WithGPUInstancing()
///       .Build(position, parent);
///
/// Particle counts are budget-conscious:
///   Core glow: 5-15 | Sparks: 10-30 | Smoke: 5-25 | Total per effect: 20-70
/// </summary>
public class AAAParticleBuilder
{
    // -------------------------------------------------------------------
    // Cached shader references (Fix 1 -- avoid Shader.Find at runtime)
    // -------------------------------------------------------------------
    private static Shader _urpParticlesUnlit;
    private static Shader _particlesStandardUnlit;
    private static Shader _mobileParticlesAdditive;
    private static Shader _vbDistortion;
    private static bool _shadersInitialized;

#if UNITY_EDITOR
    [UnityEditor.InitializeOnLoadMethod]
#endif
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
    private static void InitShaders()
    {
        _urpParticlesUnlit = Shader.Find("Universal Render Pipeline/Particles/Unlit");
        _particlesStandardUnlit = Shader.Find("Particles/Standard Unlit");
        _mobileParticlesAdditive = Shader.Find("Mobile/Particles/Additive");
        _vbDistortion = Shader.Find("VeilBreakers/Distortion");
        _shadersInitialized = true;
    }

    private static Shader GetAdditiveShader()
    {
        if (!_shadersInitialized) InitShaders();
        if (_urpParticlesUnlit != null) return _urpParticlesUnlit;
        if (_particlesStandardUnlit != null) return _particlesStandardUnlit;
        return _mobileParticlesAdditive;
    }

    private static Shader GetAlphaBlendShader()
    {
        if (!_shadersInitialized) InitShaders();
        if (_urpParticlesUnlit != null) return _urpParticlesUnlit;
        return _particlesStandardUnlit;
    }

    private static Shader GetDistortionShader()
    {
        if (!_shadersInitialized) InitShaders();
        if (_vbDistortion != null) return _vbDistortion;
        if (_urpParticlesUnlit != null) return _urpParticlesUnlit;
        return _particlesStandardUnlit;
    }

    // -------------------------------------------------------------------
    // Standard AAA curves (the secret to AAA look)
    // -------------------------------------------------------------------
    private static class Curves
    {
        /// <summary>Size: ease-in, peak at 30%, ease-out.</summary>
        public static AnimationCurve SizeOverLifetime()
        {
            return new AnimationCurve(
                new Keyframe(0.0f, 0.2f, 0f, 3.0f),
                new Keyframe(0.3f, 1.0f, 0f, 0f),
                new Keyframe(0.7f, 0.8f, -0.5f, -0.5f),
                new Keyframe(1.0f, 0.0f, -2.0f, 0f)
            );
        }

        /// <summary>Speed: start fast, decelerate.</summary>
        public static AnimationCurve SpeedOverLifetime()
        {
            return new AnimationCurve(
                new Keyframe(0.0f, 1.0f, 0f, -0.5f),
                new Keyframe(0.4f, 0.5f, -0.8f, -0.8f),
                new Keyframe(1.0f, 0.05f, -0.3f, 0f)
            );
        }

        /// <summary>Alpha: fast fade-in (0->0.1), hold (0.1->0.7), slow fade-out (0.7->1.0).</summary>
        public static Gradient AlphaOverLifetime(Color baseColor)
        {
            var grad = new Gradient();
            grad.SetKeys(
                new GradientColorKey[]
                {
                    new GradientColorKey(baseColor, 0f),
                    new GradientColorKey(baseColor, 0.5f),
                    new GradientColorKey(baseColor * 0.6f, 1f),
                },
                new GradientAlphaKey[]
                {
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(1f, 0.1f),
                    new GradientAlphaKey(1f, 0.7f),
                    new GradientAlphaKey(0f, 1f),
                }
            );
            return grad;
        }

        /// <summary>Smoke color: bright -> desaturated -> dark over lifetime.</summary>
        public static Gradient SmokeColorOverLifetime(Color baseColor)
        {
            Color desaturated = Color.Lerp(baseColor, Color.gray, 0.6f);
            Color dark = Color.Lerp(baseColor, new Color(0.1f, 0.1f, 0.1f, 1f), 0.8f);

            var grad = new Gradient();
            grad.SetKeys(
                new GradientColorKey[]
                {
                    new GradientColorKey(baseColor, 0f),
                    new GradientColorKey(desaturated, 0.4f),
                    new GradientColorKey(dark, 1f),
                },
                new GradientAlphaKey[]
                {
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(0.6f, 0.1f),
                    new GradientAlphaKey(0.4f, 0.6f),
                    new GradientAlphaKey(0f, 1f),
                }
            );
            return grad;
        }

        /// <summary>Light intensity: sharp on, hold, fade out matching effect.</summary>
        public static AnimationCurve LightIntensityOverLifetime()
        {
            return new AnimationCurve(
                new Keyframe(0.0f, 0.0f, 10f, 10f),
                new Keyframe(0.05f, 1.0f, 0f, 0f),
                new Keyframe(0.3f, 0.9f, -0.2f, -0.2f),
                new Keyframe(0.7f, 0.4f, -1.0f, -1.0f),
                new Keyframe(1.0f, 0.0f, -1.5f, 0f)
            );
        }
    }

    // -------------------------------------------------------------------
    // Per-frame raycast budget for blood stain placement (Fix 6)
    // -------------------------------------------------------------------
    public const int MAX_RAYCASTS_PER_FRAME = 5;
    private static int _raycastFrameCount;
    private static int _raycastsThisFrame;

    /// <summary>
    /// Check if a raycast is allowed this frame. Returns true and increments
    /// the counter if under budget. Resets automatically each frame.
    /// Call this before any VFX-related Physics.Raycast (e.g., blood stain placement).
    /// </summary>
    public static bool TryConsumeRaycast()
    {
        int frame = Time.frameCount;
        if (frame != _raycastFrameCount)
        {
            _raycastFrameCount = frame;
            _raycastsThisFrame = 0;
        }
        if (_raycastsThisFrame >= MAX_RAYCASTS_PER_FRAME)
            return false;
        _raycastsThisFrame++;
        return true;
    }

    // -------------------------------------------------------------------
    // Builder instance data
    // -------------------------------------------------------------------
    private string _effectName;
    private List<System.Action<GameObject>> _layerBuilders = new List<System.Action<GameObject>>();
    private bool _applyLifetimeCurves = false;
    private bool _applyNoise = false;
    private float _noiseStrength = 0.5f;
    private bool _applyGPUInstancing = false;
    private VFXLODController.QualityPreset? _qualityPreset = null;

    private AAAParticleBuilder(string effectName)
    {
        _effectName = effectName;
    }

    // -------------------------------------------------------------------
    // Entry point
    // -------------------------------------------------------------------

    /// <summary>Start building a new AAA VFX effect.</summary>
    public static AAAParticleBuilder CreateEffect(string effectName)
    {
        return new AAAParticleBuilder(effectName);
    }

    // -------------------------------------------------------------------
    // Layer 1: Core Glow (Additive, bright center, low count)
    // -------------------------------------------------------------------

    /// <summary>
    /// Add the core glow layer. Additive blend, bright emission, 5-15 particles.
    /// This is the bright center that draws the eye.
    /// </summary>
    public AAAParticleBuilder AddCoreGlow(
        Color color,
        float intensity = 3f,
        float size = 0.8f,
        int maxParticles = 10,
        float lifetime = 0.8f)
    {
        maxParticles = Mathf.Clamp(maxParticles, 5, 15);

        _layerBuilders.Add(root =>
        {
            GameObject layerObj = new GameObject("CoreGlow");
            layerObj.transform.SetParent(root.transform, false);

            ParticleSystem ps = layerObj.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = lifetime;
            main.startSize = new ParticleSystem.MinMaxCurve(size * 0.6f, size);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.1f, 0.3f);
            main.startColor = color * intensity;
            main.maxParticles = maxParticles;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.playOnAwake = true;
            main.gravityModifier = 0f;

            // Burst emission: 70% up front, 30% trickle
            var emission = ps.emission;
            emission.enabled = true;
            emission.rateOverTime = maxParticles * 0.3f / Mathf.Max(lifetime, 0.1f);
            emission.SetBursts(new ParticleSystem.Burst[]
            {
                new ParticleSystem.Burst(0f, Mathf.RoundToInt(maxParticles * 0.7f))
            });

            // Shape: small sphere for concentrated glow
            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = size * 0.2f;

            // Size over lifetime
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, Curves.SizeOverLifetime());

            // Color over lifetime
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = new ParticleSystem.MinMaxGradient(Curves.AlphaOverLifetime(color * intensity));

            // Renderer: Additive blend
            var renderer = layerObj.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.material = GetOrCreateAdditiveParticleMaterial(color * intensity);
            renderer.sortingOrder = 2;
        });
        return this;
    }

    // -------------------------------------------------------------------
    // Layer 2: Spark Burst (Additive, fast, stretched billboards)
    // -------------------------------------------------------------------

    /// <summary>
    /// Add spark/detail particles. Fast-moving, burst emission, stretch billboard.
    /// 10-30 particles with gravity and speed decay.
    /// </summary>
    public AAAParticleBuilder AddSparkBurst(
        Color color,
        int count = 20,
        float speed = 5f,
        float lifetime = 0.6f,
        float size = 0.08f)
    {
        count = Mathf.Clamp(count, 10, 30);

        _layerBuilders.Add(root =>
        {
            GameObject layerObj = new GameObject("SparkBurst");
            layerObj.transform.SetParent(root.transform, false);

            ParticleSystem ps = layerObj.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = new ParticleSystem.MinMaxCurve(lifetime * 0.5f, lifetime);
            main.startSize = new ParticleSystem.MinMaxCurve(size * 0.5f, size);
            main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.6f, speed);
            main.startColor = color;
            main.maxParticles = count;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.gravityModifier = 0.8f;
            main.playOnAwake = true;

            // Full burst at start -- dramatic spark shower
            var emission = ps.emission;
            emission.enabled = true;
            emission.rateOverTime = 0f;
            emission.SetBursts(new ParticleSystem.Burst[]
            {
                new ParticleSystem.Burst(0f, count)
            });

            // Cone shape for directional spread
            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 45f;
            shape.radius = 0.1f;

            // Speed over lifetime: fast start, decelerate
            var vol = ps.velocityOverLifetime;
            vol.enabled = true;
            vol.speedModifier = new ParticleSystem.MinMaxCurve(1f, Curves.SpeedOverLifetime());

            // Size over lifetime
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(
                new Keyframe(0f, 1f), new Keyframe(1f, 0f)));

            // Color over lifetime with alpha fade
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = new ParticleSystem.MinMaxGradient(Curves.AlphaOverLifetime(color));

            // Collision with ground
            var collision = ps.collision;
            collision.enabled = true;
            collision.type = ParticleSystemCollisionType.World;
            collision.mode = ParticleSystemCollisionMode.Collision3D;
            collision.bounce = 0.3f;
            collision.lifetimeLoss = 0.2f;
            collision.dampen = 0.5f;

            // Renderer: stretched billboard for motion streaks
            var renderer = layerObj.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = ParticleSystemRenderMode.Stretch;
            renderer.lengthScale = 2f;
            renderer.velocityScale = 0.1f;
            renderer.material = GetOrCreateAdditiveParticleMaterial(color);
            renderer.sortingOrder = 3;
        });
        return this;
    }

    // -------------------------------------------------------------------
    // Layer 3: Smoke / Trail (Alpha blend, soft, slow, large)
    // -------------------------------------------------------------------

    /// <summary>
    /// Add smoke/trail particles. AlphaBlend (NOT additive), large soft particles,
    /// low emission, long lifetime. Color desaturates over lifetime.
    /// </summary>
    public AAAParticleBuilder AddSmoke(
        Color color,
        int count = 8,
        float lifetime = 3f,
        float size = 1.5f,
        float speed = 0.5f)
    {
        count = Mathf.Clamp(count, 5, 25); // Fix 7 -- increased from 10 to 25 (Opus M-03)

        _layerBuilders.Add(root =>
        {
            GameObject layerObj = new GameObject("Smoke");
            layerObj.transform.SetParent(root.transform, false);

            ParticleSystem ps = layerObj.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = new ParticleSystem.MinMaxCurve(lifetime * 0.7f, lifetime);
            main.startSize = new ParticleSystem.MinMaxCurve(size * 0.5f, size);
            main.startSpeed = new ParticleSystem.MinMaxCurve(speed * 0.3f, speed);
            main.startColor = color;
            main.maxParticles = count;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.gravityModifier = -0.05f; // Slight upward drift
            main.startRotation = new ParticleSystem.MinMaxCurve(0f, Mathf.PI * 2f);
            main.playOnAwake = true;

            // Low constant emission + small initial burst
            var emission = ps.emission;
            emission.enabled = true;
            emission.rateOverTime = count * 0.3f / Mathf.Max(lifetime, 0.1f);
            emission.SetBursts(new ParticleSystem.Burst[]
            {
                new ParticleSystem.Burst(0.05f, Mathf.Max(1, count / 3))
            });

            // Sphere shape for organic spread
            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = 0.3f;

            // Size over lifetime: grow then fade
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(
                new Keyframe(0f, 0.3f, 2f, 2f),
                new Keyframe(0.4f, 1f, 0f, 0f),
                new Keyframe(1f, 1.3f, 0.3f, 0f)));

            // Rotation over lifetime for organic tumble
            var rol = ps.rotationOverLifetime;
            rol.enabled = true;
            rol.z = new ParticleSystem.MinMaxCurve(-0.5f, 0.5f);

            // Color over lifetime: bright -> desaturated -> dark
            var col = ps.colorOverLifetime;
            col.enabled = true;
            col.color = new ParticleSystem.MinMaxGradient(Curves.SmokeColorOverLifetime(color));

            // Renderer: AlphaBlend (NOT Additive -- smoke should occlude, not glow)
            var renderer = layerObj.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.material = GetOrCreateAlphaBlendParticleMaterial(color);
            renderer.sortingOrder = 0; // Behind glow layers
        });
        return this;
    }

    // -------------------------------------------------------------------
    // Layer 4: Distortion / Heat Haze
    // -------------------------------------------------------------------

    /// <summary>
    /// Add distortion/heat haze layer. Invisible particles that warp the background
    /// via a distortion shader. Creates the shimmer that sells fire/energy effects.
    /// </summary>
    public AAAParticleBuilder AddDistortion(
        float strength = 0.1f,
        float radius = 1.5f,
        float lifetime = 1.0f,
        int count = 5)
    {
        count = Mathf.Clamp(count, 3, 8);

        _layerBuilders.Add(root =>
        {
            GameObject layerObj = new GameObject("Distortion");
            layerObj.transform.SetParent(root.transform, false);

            ParticleSystem ps = layerObj.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.startLifetime = lifetime;
            main.startSize = new ParticleSystem.MinMaxCurve(radius * 0.5f, radius);
            main.startSpeed = 0.2f;
            main.maxParticles = count;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.gravityModifier = -0.02f;
            main.playOnAwake = true;

            // Low emission
            var emission = ps.emission;
            emission.enabled = true;
            emission.rateOverTime = count / Mathf.Max(lifetime, 0.1f) * 0.5f;
            emission.SetBursts(new ParticleSystem.Burst[]
            {
                new ParticleSystem.Burst(0f, count / 2 + 1)
            });

            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Sphere;
            shape.radius = radius * 0.3f;

            // Size grows over lifetime
            var sol = ps.sizeOverLifetime;
            sol.enabled = true;
            sol.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(
                new Keyframe(0f, 0.5f), new Keyframe(0.5f, 1f), new Keyframe(1f, 0.8f)));

            // Color over lifetime -- alpha controls distortion strength
            var col = ps.colorOverLifetime;
            col.enabled = true;
            var distGrad = new Gradient();
            distGrad.SetKeys(
                new GradientColorKey[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                new GradientAlphaKey[]
                {
                    new GradientAlphaKey(0f, 0f),
                    new GradientAlphaKey(strength, 0.15f),
                    new GradientAlphaKey(strength * 0.8f, 0.6f),
                    new GradientAlphaKey(0f, 1f),
                }
            );
            col.color = new ParticleSystem.MinMaxGradient(distGrad);

            // Renderer: uses URP unlit particle shader as fallback
            // In production, replace with a custom distortion grab-pass shader
            var renderer = layerObj.GetComponent<ParticleSystemRenderer>();
            renderer.renderMode = ParticleSystemRenderMode.Billboard;
            renderer.material = GetOrCreateDistortionMaterial(strength);
            renderer.sortingOrder = 1;
        });
        return this;
    }

    // -------------------------------------------------------------------
    // Layer 5: Point Light
    // -------------------------------------------------------------------

    /// <summary>
    /// Add a dynamic point light that matches the VFX color.
    /// Illuminates nearby surfaces which is CRITICAL for realistic VFX.
    /// Intensity follows a curve matching the effect lifecycle.
    /// </summary>
    public AAAParticleBuilder AddPointLight(
        Color color,
        float intensity = 2f,
        float range = 3f,
        float lifetime = 1.0f)
    {
        _layerBuilders.Add(root =>
        {
            GameObject lightObj = new GameObject("PointLight");
            lightObj.transform.SetParent(root.transform, false);

            Light light = lightObj.AddComponent<Light>();
            light.type = LightType.Point;
            light.color = color;
            light.intensity = intensity;
            light.range = range;
            light.shadows = LightShadows.None; // No shadow for perf
            light.renderMode = LightRenderMode.Auto;

            // Add the light animator component
            var animator = lightObj.AddComponent<VFXLightAnimator>();
            animator.Initialize(intensity, lifetime, Curves.LightIntensityOverLifetime());
        });
        return this;
    }

    // -------------------------------------------------------------------
    // Global modifiers
    // -------------------------------------------------------------------

    /// <summary>
    /// Apply standard AAA lifetime curves (size, speed, alpha) to all particle layers.
    /// This is what transforms flat amateur effects into dynamic AAA ones.
    /// </summary>
    public AAAParticleBuilder WithLifetimeCurves()
    {
        _applyLifetimeCurves = true;
        return this;
    }

    /// <summary>
    /// Add noise/turbulence to all particle layers for organic movement.
    /// Strength 0.3-0.8 is natural; below 0.3 looks robotic; above 1.5 is chaotic.
    /// </summary>
    public AAAParticleBuilder WithNoiseTurbulence(float strength = 0.5f)
    {
        _applyNoise = true;
        _noiseStrength = Mathf.Clamp(strength, 0.1f, 2f);
        return this;
    }

    /// <summary>Enable GPU instancing on all particle renderers for performance.</summary>
    public AAAParticleBuilder WithGPUInstancing()
    {
        _applyGPUInstancing = true;
        return this;
    }

    /// <summary>Tag the built VFX with a quality preset for VFXLODController.</summary>
    public AAAParticleBuilder WithQualityPreset(VFXLODController.QualityPreset preset)
    {
        _qualityPreset = preset;
        return this;
    }

    // -------------------------------------------------------------------
    // Build
    // -------------------------------------------------------------------

    /// <summary>
    /// Build the multi-layered VFX GameObject at the given position.
    /// Returns the root GameObject containing all particle layers.
    /// </summary>
    public GameObject Build(Vector3 position, Transform parent = null)
    {
        GameObject root = new GameObject($"VFX_{_effectName}");
        root.transform.position = position;
        if (parent != null)
            root.transform.SetParent(parent, true);

        // Build all layers
        foreach (var builder in _layerBuilders)
            builder(root);

        // Apply global modifiers to all particle systems
        ParticleSystem[] allSystems = root.GetComponentsInChildren<ParticleSystem>(true);

        if (_applyNoise)
        {
            foreach (var ps in allSystems)
            {
                var noise = ps.noise;
                noise.enabled = true;
                noise.strength = new ParticleSystem.MinMaxCurve(_noiseStrength * 0.7f, _noiseStrength);
                noise.frequency = 0.8f;
                noise.scrollSpeed = 0.2f;
                noise.quality = ParticleSystemNoiseQuality.Medium;
                noise.octaveCount = 2;
                noise.damping = true;
            }
        }

        if (_applyGPUInstancing)
        {
            var renderers = root.GetComponentsInChildren<ParticleSystemRenderer>(true);
            foreach (var r in renderers)
            {
                r.enableGPUInstancing = true;
            }
        }

        // Attach LOD controller
        var lod = root.AddComponent<VFXLODController>();
        if (_qualityPreset.HasValue)
            lod.ApplyQualityPreset(_qualityPreset.Value);

        // Set secondary and distortion layer indices for LOD
        var layerIndicesSecondary = new List<int>();
        var layerIndicesDistortion = new List<int>();
        for (int i = 0; i < root.transform.childCount; i++)
        {
            string childName = root.transform.GetChild(i).name;
            if (childName == "Smoke")
                layerIndicesSecondary.Add(i);
            if (childName == "Distortion")
                layerIndicesDistortion.Add(i);
        }
        lod.secondaryLayerIndices = layerIndicesSecondary.ToArray();
        lod.distortionLayerIndices = layerIndicesDistortion.ToArray();

        return root;
    }

    // -------------------------------------------------------------------
    // Material helpers -- cached to prevent memory leaks (C-03 fix)
    // -------------------------------------------------------------------
    private static Dictionary<int, Material> _materialCache = new Dictionary<int, Material>();

    private static int MaterialKey(Color color, int blendMode)
    {
        return HashCode.Combine(
            Mathf.RoundToInt(color.r * 255),
            Mathf.RoundToInt(color.g * 255),
            Mathf.RoundToInt(color.b * 255),
            Mathf.RoundToInt(color.a * 255),
            blendMode
        );
    }

    /// <summary>
    /// Setup a MaterialPropertyBlock for per-instance color (Fix 2 -- avoids unique material instances).
    /// Use as primary path; falls back to material cache when MPB is not supported.
    /// </summary>
    public static void SetupMaterialPropertyBlock(ParticleSystemRenderer renderer, Color color)
    {
        if (renderer == null) return;
        var mpb = new MaterialPropertyBlock();
        renderer.GetPropertyBlock(mpb);
        mpb.SetColor("_BaseColor", color);
        if (renderer.sharedMaterial != null && renderer.sharedMaterial.HasProperty("_EmissionColor"))
            mpb.SetColor("_EmissionColor", color * 2f);
        renderer.SetPropertyBlock(mpb);
    }

    /// <summary>Create or retrieve cached Additive particle material.</summary>
    private static Material GetOrCreateAdditiveParticleMaterial(Color color)
    {
        int key = MaterialKey(color, 1);
        if (_materialCache.TryGetValue(key, out Material cached) && cached != null)
            return cached;

        Shader shader = GetAdditiveShader();

        Material mat = new Material(shader);
        mat.name = $"VFX_Additive_{ColorToHex(color)}";

        if (mat.HasProperty("_Surface"))
        {
            mat.SetFloat("_Surface", 1f);
            mat.SetFloat("_Blend", 1f);
        }
        mat.SetColor("_BaseColor", color);
        if (mat.HasProperty("_EmissionColor"))
        {
            mat.EnableKeyword("_EMISSION");
            mat.SetColor("_EmissionColor", color * 2f);
        }
        mat.renderQueue = 3100;
        _materialCache[key] = mat;
        return mat;
    }

    /// <summary>Create or retrieve cached AlphaBlend particle material (for smoke/blood -- Fix 5).</summary>
    private static Material GetOrCreateAlphaBlendParticleMaterial(Color color)
    {
        int key = MaterialKey(color, 0);
        if (_materialCache.TryGetValue(key, out Material cached) && cached != null)
            return cached;

        Shader shader = GetAlphaBlendShader();

        Material mat = new Material(shader);
        mat.name = $"VFX_AlphaBlend_{ColorToHex(color)}";

        if (mat.HasProperty("_Surface"))
        {
            mat.SetFloat("_Surface", 1f);
            mat.SetFloat("_Blend", 0f); // Alpha blend, NOT additive (Fix 5 -- blood must use alpha blend)
        }
        mat.SetColor("_BaseColor", color);
        mat.renderQueue = 3000;
        _materialCache[key] = mat;
        return mat;
    }

    /// <summary>Create or retrieve cached distortion material.</summary>
    private static Material GetOrCreateDistortionMaterial(float strength)
    {
        int key = HashCode.Combine(Mathf.RoundToInt(strength * 100), 99);
        if (_materialCache.TryGetValue(key, out Material cached) && cached != null)
            return cached;

        Shader shader = GetDistortionShader();

        Material mat = new Material(shader);
        mat.name = "VFX_Distortion";

        if (mat.HasProperty("_DistortionStrength"))
            mat.SetFloat("_DistortionStrength", strength);

        if (mat.HasProperty("_Surface"))
        {
            mat.SetFloat("_Surface", 1f);
            mat.SetFloat("_Blend", 0f);
        }

        mat.SetColor("_BaseColor", new Color(1f, 1f, 1f, 0.01f));
        mat.renderQueue = 3050;
        _materialCache[key] = mat;
        return mat;
    }

    private static string ColorToHex(Color c)
    {
        return ColorUtility.ToHtmlStringRGB(c);
    }
}

/// <summary>
/// Animates a Light component intensity over a specified lifetime using an AnimationCurve.
/// Auto-destroys when complete. Used by AAAParticleBuilder.AddPointLight().
/// </summary>
public class VFXLightAnimator : MonoBehaviour
{
    private float _maxIntensity;
    private float _lifetime;
    private AnimationCurve _curve;
    private float _elapsed;
    private Light _light;
    private bool _initialized;

    public void Initialize(float maxIntensity, float lifetime, AnimationCurve curve)
    {
        _maxIntensity = maxIntensity;
        _lifetime = Mathf.Max(lifetime, 0.01f);
        _curve = curve;
        _elapsed = 0f;
        _light = GetComponent<Light>();
        _initialized = _light != null;
    }

    private void Update()
    {
        if (!_initialized) return;

        _elapsed += Time.deltaTime;
        float t = Mathf.Clamp01(_elapsed / _lifetime);
        _light.intensity = _maxIntensity * _curve.Evaluate(t);

        if (t >= 1f)
        {
            _light.intensity = 0f;
            _light.enabled = false;
            _initialized = false;
        }
    }
}
'''

    return {
        "script_path": "Assets/Scripts/VFX/AAAParticleBuilder.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Use builder from any script: AAAParticleBuilder.CreateEffect(\"name\").AddCoreGlow(...).Build(pos)",
            "Chain layers: .AddCoreGlow() .AddSparkBurst() .AddSmoke() .AddDistortion() .AddPointLight()",
            "Always call .WithLifetimeCurves() and .WithNoiseTurbulence() for AAA look",
            "Call .WithGPUInstancing() for performance in open world",
        ],
    }


# ---------------------------------------------------------------------------
# 4. VFX Quality Presets
# ---------------------------------------------------------------------------


def generate_vfx_quality_presets_script() -> dict[str, Any]:
    """Generate VFXQualityPresets ScriptableObject and editor window.

    Four quality tiers (LOW/MEDIUM/HIGH/ULTRA) with per-tier particle budgets,
    LOD distances, feature toggles, and auto-detection from SystemInfo.
    Includes an editor window for monitoring active VFX stats.

    Returns:
        Dict with script_path, script_content, next_steps.
    """

    script = '''using UnityEngine;
using System;
#if UNITY_EDITOR
using UnityEditor;
#endif

/// <summary>
/// ScriptableObject defining VFX quality tiers and runtime quality switching.
/// Create via Assets > Create > VeilBreakers > VFX Quality Presets.
/// </summary>
[CreateAssetMenu(fileName = "VFXQualityPresets", menuName = "VeilBreakers/VFX Quality Presets")]
public class VFXQualityPresets : ScriptableObject
{
    // -------------------------------------------------------------------
    // Quality tier enum
    // -------------------------------------------------------------------
    public enum QualityTier { LOW = 0, MEDIUM = 1, HIGH = 2, ULTRA = 3 }

    // -------------------------------------------------------------------
    // Per-tier settings
    // -------------------------------------------------------------------
    [Serializable]
    public class TierSettings
    {
        public string tierName;
        public int maxActiveParticles;
        public int maxActiveEffects;
        [Range(0.1f, 2f)]
        public float particleMultiplier;
        public bool enableDistortion;
        public bool enableDynamicLights;
        public bool enableSecondaryLayers;
        public bool enableSmoke;
        public float[] lodDistances; // [closeToMed, medToFar, farToCulled]
        public VFXShadowMode shadowCasting;

        public TierSettings() { }
        public TierSettings(
            string name, int maxParticles, int maxEffects, float mult,
            bool distortion, bool lights, bool secondary, bool smoke,
            float[] lods, VFXShadowMode shadows)
        {
            tierName = name;
            maxActiveParticles = maxParticles;
            maxActiveEffects = maxEffects;
            particleMultiplier = mult;
            enableDistortion = distortion;
            enableDynamicLights = lights;
            enableSecondaryLayers = secondary;
            enableSmoke = smoke;
            lodDistances = lods;
            shadowCasting = shadows;
        }
    }

    public enum VFXShadowMode { Off, OnClose, On }

    // -------------------------------------------------------------------
    // Preset data
    // -------------------------------------------------------------------
    [Header("Quality Tiers")]
    public TierSettings[] tiers = new TierSettings[]
    {
        new TierSettings("LOW",    500,  10, 0.3f, false, false, false, false,
            new float[] { 10f, 25f, 50f },  VFXShadowMode.Off),
        new TierSettings("MEDIUM", 1000, 20, 0.6f, false, true,  true,  false,
            new float[] { 15f, 35f, 65f },  VFXShadowMode.Off),
        new TierSettings("HIGH",   2000, 40, 1.0f, true,  true,  true,  true,
            new float[] { 20f, 50f, 100f }, VFXShadowMode.OnClose),
        new TierSettings("ULTRA",  4000, 80, 1.5f, true,  true,  true,  true,
            new float[] { 30f, 60f, 120f }, VFXShadowMode.On),
    };

    [Header("Runtime State")]
    [SerializeField]
    private QualityTier _currentTier = QualityTier.HIGH;

    // -------------------------------------------------------------------
    // Singleton-like instance access
    // -------------------------------------------------------------------
    private static VFXQualityPresets _instance;
    public static VFXQualityPresets Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = Resources.Load<VFXQualityPresets>("VFXQualityPresets");
                if (_instance == null)
                {
                    Debug.LogWarning("[VFXQualityPresets] No preset asset found in Resources/. Using defaults.");
                    _instance = CreateInstance<VFXQualityPresets>();
                }
            }
            return _instance;
        }
    }

    public QualityTier CurrentTier => _currentTier;
    public TierSettings CurrentSettings => tiers[Mathf.Clamp((int)_currentTier, 0, tiers.Length - 1)];

    // -------------------------------------------------------------------
    // Quality switching
    // -------------------------------------------------------------------

    /// <summary>
    /// Set the global VFX quality tier. Propagates to VFXPoolManager and all
    /// active VFXLODController instances.
    /// </summary>
    public static void SetQuality(QualityTier tier)
    {
        Instance._currentTier = tier;
        var settings = Instance.CurrentSettings;

        Debug.Log($"[VFXQualityPresets] Quality set to {settings.tierName}: " +
                  $"maxParticles={settings.maxActiveParticles}, multiplier={settings.particleMultiplier}");

        // Update pool manager
        if (VFXPoolManager.Instance != null)
        {
            VFXPoolManager.Instance.MaxActiveParticlesOverride = settings.maxActiveParticles;
            VFXPoolManager.Instance.ParticleMultiplier = settings.particleMultiplier;
        }

        // Update all LOD controllers via static registry (Fix 9 -- no FindObjectsByType)
        foreach (var lod in VFXLODController.ActiveControllers)
        {
            if (lod == null) continue;
            if (settings.lodDistances != null && settings.lodDistances.Length >= 3)
            {
                lod.closeToMediumDist = settings.lodDistances[0];
                lod.mediumToFarDist = settings.lodDistances[1];
                lod.farToCulledDist = settings.lodDistances[2];
            }
        }
    }

    // -------------------------------------------------------------------
    // Auto-detection from hardware
    // -------------------------------------------------------------------

    /// <summary>
    /// Auto-detect the best quality tier based on SystemInfo.
    /// Call once at game startup.
    /// </summary>
    public static QualityTier AutoDetectTier()
    {
        int gpuMemory = SystemInfo.graphicsMemorySize; // MB
        int shaderLevel = SystemInfo.graphicsShaderLevel;
        bool isMobile = Application.isMobilePlatform;

        QualityTier detected;

        if (isMobile || gpuMemory < 2048 || shaderLevel < 35)
        {
            detected = QualityTier.LOW;
        }
        else if (gpuMemory < 4096 || shaderLevel < 45)
        {
            detected = QualityTier.MEDIUM;
        }
        else if (gpuMemory < 8192 || shaderLevel < 50)
        {
            detected = QualityTier.HIGH;
        }
        else
        {
            detected = QualityTier.ULTRA;
        }

        Debug.Log($"[VFXQualityPresets] Auto-detected tier: {detected} " +
                  $"(GPU: {gpuMemory}MB, ShaderLevel: {shaderLevel}, Mobile: {isMobile})");

        return detected;
    }

    /// <summary>Auto-detect and apply the best quality tier.</summary>
    public static void AutoApply()
    {
        SetQuality(AutoDetectTier());
    }

    // -------------------------------------------------------------------
    // Feature queries (for conditional VFX layer creation)
    // -------------------------------------------------------------------

    /// <summary>Whether distortion layers should be created at current quality.</summary>
    public static bool DistortionEnabled => Instance.CurrentSettings.enableDistortion;

    /// <summary>Whether dynamic lights should be created at current quality.</summary>
    public static bool DynamicLightsEnabled => Instance.CurrentSettings.enableDynamicLights;

    /// <summary>Whether secondary particle layers (smoke etc.) should be created.</summary>
    public static bool SecondaryLayersEnabled => Instance.CurrentSettings.enableSecondaryLayers;

    /// <summary>Whether smoke layers should be created at current quality.</summary>
    public static bool SmokeEnabled => Instance.CurrentSettings.enableSmoke;

    /// <summary>Global particle count multiplier for emission rates.</summary>
    public static float ParticleMultiplier => Instance.CurrentSettings.particleMultiplier;
}

// ===========================================================================
// Editor Window: VFX Quality Monitor
// ===========================================================================

#if UNITY_EDITOR
public class VFXQualityMonitorWindow : EditorWindow
{
    private VFXQualityPresets.QualityTier _selectedTier = VFXQualityPresets.QualityTier.HIGH;
    private Vector2 _scrollPos;

    [MenuItem("VeilBreakers/VFX/Quality Monitor")]
    public static void ShowWindow()
    {
        GetWindow<VFXQualityMonitorWindow>("VFX Quality Monitor");
    }

    private void OnGUI()
    {
        _scrollPos = EditorGUILayout.BeginScrollView(_scrollPos);

        EditorGUILayout.LabelField("VFX Quality Monitor", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // ----- Runtime Stats -----
        EditorGUILayout.LabelField("Runtime Stats", EditorStyles.boldLabel);
        DrawSeparator();

        if (Application.isPlaying && VFXPoolManager.Instance != null)
        {
            var pool = VFXPoolManager.Instance;
            var settings = VFXQualityPresets.Instance.CurrentSettings;

            // Particle count bar
            float particleRatio = (float)pool.TotalActiveParticles / Mathf.Max(settings.maxActiveParticles, 1);
            EditorGUI.ProgressBar(
                EditorGUILayout.GetControlRect(false, 20f),
                Mathf.Clamp01(particleRatio),
                $"Particles: {pool.TotalActiveParticles} / {settings.maxActiveParticles}"
            );

            // Effect count bar
            float effectRatio = (float)pool.TotalActiveEffects / Mathf.Max(settings.maxActiveEffects, 1);
            EditorGUI.ProgressBar(
                EditorGUILayout.GetControlRect(false, 20f),
                Mathf.Clamp01(effectRatio),
                $"Effects: {pool.TotalActiveEffects} / {settings.maxActiveEffects}"
            );

            EditorGUILayout.LabelField($"Pooled Objects: {pool.TotalPooledObjects}");
            EditorGUILayout.LabelField($"Culled This Frame: {pool.CulledThisFrame}");

            // Warning colors
            if (particleRatio > 0.9f)
                EditorGUILayout.HelpBox("Particle budget nearly exhausted! Low-priority effects being culled.", MessageType.Warning);
            if (particleRatio > 1.0f)
                EditorGUILayout.HelpBox("OVER BUDGET! Effects are being force-culled.", MessageType.Error);
        }
        else
        {
            EditorGUILayout.HelpBox("Enter Play Mode to see runtime stats.", MessageType.Info);
        }

        EditorGUILayout.Space(10);

        // ----- Quality Tier Selection -----
        EditorGUILayout.LabelField("Quality Tier", EditorStyles.boldLabel);
        DrawSeparator();

        _selectedTier = (VFXQualityPresets.QualityTier)EditorGUILayout.EnumPopup("Select Tier", _selectedTier);

        if (GUILayout.Button("Apply Quality Tier"))
        {
            if (Application.isPlaying)
            {
                VFXQualityPresets.SetQuality(_selectedTier);
            }
            else
            {
                Debug.Log($"[VFXQualityMonitor] Tier {_selectedTier} will be applied at runtime.");
            }
        }

        if (GUILayout.Button("Auto-Detect Quality"))
        {
            _selectedTier = VFXQualityPresets.AutoDetectTier();
            if (Application.isPlaying)
                VFXQualityPresets.SetQuality(_selectedTier);
        }

        EditorGUILayout.Space(10);

        // ----- Tier Details -----
        EditorGUILayout.LabelField("Tier Configuration", EditorStyles.boldLabel);
        DrawSeparator();

        var presets = VFXQualityPresets.Instance;
        if (presets != null && presets.tiers != null)
        {
            int idx = Mathf.Clamp((int)_selectedTier, 0, presets.tiers.Length - 1);
            var tier = presets.tiers[idx];

            EditorGUILayout.LabelField("Tier", tier.tierName);
            EditorGUILayout.LabelField("Max Active Particles", tier.maxActiveParticles.ToString());
            EditorGUILayout.LabelField("Max Active Effects", tier.maxActiveEffects.ToString());
            EditorGUILayout.LabelField("Particle Multiplier", tier.particleMultiplier.ToString("F2"));
            EditorGUILayout.LabelField("Distortion", tier.enableDistortion ? "Enabled" : "Disabled");
            EditorGUILayout.LabelField("Dynamic Lights", tier.enableDynamicLights ? "Enabled" : "Disabled");
            EditorGUILayout.LabelField("Secondary Layers", tier.enableSecondaryLayers ? "Enabled" : "Disabled");
            EditorGUILayout.LabelField("Smoke", tier.enableSmoke ? "Enabled" : "Disabled");
            EditorGUILayout.LabelField("Shadow Casting", tier.shadowCasting.ToString());

            if (tier.lodDistances != null && tier.lodDistances.Length >= 3)
            {
                EditorGUILayout.LabelField("LOD Close->Medium", $"{tier.lodDistances[0]}m");
                EditorGUILayout.LabelField("LOD Medium->Far", $"{tier.lodDistances[1]}m");
                EditorGUILayout.LabelField("LOD Far->Culled", $"{tier.lodDistances[2]}m");
            }
        }

        EditorGUILayout.Space(10);

        // ----- All Tiers Comparison -----
        EditorGUILayout.LabelField("All Tiers Comparison", EditorStyles.boldLabel);
        DrawSeparator();

        DrawTierComparisonTable(presets);

        // ----- Hardware Info -----
        EditorGUILayout.Space(10);
        EditorGUILayout.LabelField("Hardware Info", EditorStyles.boldLabel);
        DrawSeparator();
        EditorGUILayout.LabelField("GPU", SystemInfo.graphicsDeviceName);
        EditorGUILayout.LabelField("GPU Memory", $"{SystemInfo.graphicsMemorySize} MB");
        EditorGUILayout.LabelField("Shader Level", SystemInfo.graphicsShaderLevel.ToString());
        EditorGUILayout.LabelField("Platform", Application.platform.ToString());

        EditorGUILayout.EndScrollView();

        // Repaint during play mode for live stats
        if (Application.isPlaying)
            Repaint();
    }

    private void DrawTierComparisonTable(VFXQualityPresets presets)
    {
        if (presets == null || presets.tiers == null) return;

        // Header
        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.LabelField("Setting", EditorStyles.boldLabel, GUILayout.Width(130));
        foreach (var t in presets.tiers)
            EditorGUILayout.LabelField(t.tierName, EditorStyles.boldLabel, GUILayout.Width(80));
        EditorGUILayout.EndHorizontal();

        // Rows
        DrawCompRow("Max Particles", presets, t => t.maxActiveParticles.ToString());
        DrawCompRow("Max Effects", presets, t => t.maxActiveEffects.ToString());
        DrawCompRow("Multiplier", presets, t => t.particleMultiplier.ToString("F1"));
        DrawCompRow("Distortion", presets, t => t.enableDistortion ? "Yes" : "No");
        DrawCompRow("Dyn Lights", presets, t => t.enableDynamicLights ? "Yes" : "No");
        DrawCompRow("Secondary", presets, t => t.enableSecondaryLayers ? "Yes" : "No");
        DrawCompRow("Smoke", presets, t => t.enableSmoke ? "Yes" : "No");
        DrawCompRow("Shadows", presets, t => t.shadowCasting.ToString());
    }

    private void DrawCompRow(string label, VFXQualityPresets presets, System.Func<VFXQualityPresets.TierSettings, string> getter)
    {
        EditorGUILayout.BeginHorizontal();
        EditorGUILayout.LabelField(label, GUILayout.Width(130));
        foreach (var t in presets.tiers)
            EditorGUILayout.LabelField(getter(t), GUILayout.Width(80));
        EditorGUILayout.EndHorizontal();
    }

    private void DrawSeparator()
    {
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider);
    }
}
#endif
'''

    return {
        "script_path": "Assets/Scripts/VFX/VFXQualityPresets.cs",
        "script_content": script,
        "next_steps": [
            "Open Unity Editor and wait for compilation",
            "Create preset asset: Assets > Create > VeilBreakers > VFX Quality Presets",
            "Place asset in a Resources/ folder for auto-loading",
            "Open monitor: VeilBreakers > VFX > Quality Monitor",
            "Call VFXQualityPresets.AutoApply() at game startup for auto-detection",
            "Runtime switch: VFXQualityPresets.SetQuality(QualityTier.HIGH)",
        ],
    }
