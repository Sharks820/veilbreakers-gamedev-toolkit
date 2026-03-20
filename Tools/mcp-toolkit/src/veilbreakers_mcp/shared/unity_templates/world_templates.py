"""World and scene management C# template generators for Unity automation.

Each function returns a complete C# source string (or tuple for multi-file
generators) that can be written to Unity project directories.  Editor scripts
go to ``Assets/Editor/Generated/World/`` and register under the
``VeilBreakers/World/...`` MenuItem menu.  Runtime MonoBehaviours go to
``Assets/Scripts/Runtime/WorldSystems/``.

Exports:
    generate_scene_creation_script       -- SCNE-01: scene creation + async loading
    generate_scene_transition_script     -- SCNE-02: scene transition system (returns tuple)
    generate_probe_setup_script          -- SCNE-03: reflection probes + light probes
    generate_occlusion_setup_script      -- SCNE-04: occlusion culling setup
    generate_environment_setup_script    -- SCNE-05: HDR skybox + GI
    generate_terrain_detail_script       -- SCNE-06: terrain detail painting
    generate_tilemap_setup_script        -- TWO-01: tilemap + rule tiles
    generate_2d_physics_script           -- TWO-02: 2D physics configuration
    generate_time_of_day_preset_script   -- WORLD-08: 8 time-of-day presets

Note: ``generate_scene_transition_script`` returns a **tuple** of two strings
(editor_cs, runtime_cs).  All other generators return a single string.
"""

from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Sanitisation helpers (local copies -- avoids circular imports)
# ---------------------------------------------------------------------------

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
# Time-of-day lighting presets (8 presets -- dark fantasy aesthetic)
# ---------------------------------------------------------------------------

_WORLD_TIME_PRESETS: dict[str, dict] = {
    "dawn": {
        "sun_rotation_x": 8.0,
        "sun_rotation_y": 170.0,
        "sun_color": [1.0, 0.65, 0.35],
        "sun_intensity": 0.7,
        "ambient_color": [0.28, 0.22, 0.32],
        "fog_color": [0.55, 0.42, 0.48],
        "fog_density": 0.012,
    },
    "morning": {
        "sun_rotation_x": 25.0,
        "sun_rotation_y": 170.0,
        "sun_color": [1.0, 0.85, 0.65],
        "sun_intensity": 1.0,
        "ambient_color": [0.35, 0.32, 0.38],
        "fog_color": [0.6, 0.55, 0.55],
        "fog_density": 0.008,
    },
    "noon": {
        "sun_rotation_x": 60.0,
        "sun_rotation_y": 170.0,
        "sun_color": [1.0, 0.95, 0.88],
        "sun_intensity": 1.4,
        "ambient_color": [0.4, 0.42, 0.48],
        "fog_color": [0.65, 0.68, 0.72],
        "fog_density": 0.004,
    },
    "afternoon": {
        "sun_rotation_x": 40.0,
        "sun_rotation_y": 250.0,
        "sun_color": [1.0, 0.88, 0.72],
        "sun_intensity": 1.2,
        "ambient_color": [0.38, 0.35, 0.4],
        "fog_color": [0.6, 0.55, 0.52],
        "fog_density": 0.006,
    },
    "dusk": {
        "sun_rotation_x": 5.0,
        "sun_rotation_y": 350.0,
        "sun_color": [1.0, 0.42, 0.18],
        "sun_intensity": 0.5,
        "ambient_color": [0.22, 0.12, 0.18],
        "fog_color": [0.45, 0.28, 0.22],
        "fog_density": 0.015,
    },
    "evening": {
        "sun_rotation_x": -5.0,
        "sun_rotation_y": 350.0,
        "sun_color": [0.6, 0.35, 0.25],
        "sun_intensity": 0.3,
        "ambient_color": [0.12, 0.08, 0.14],
        "fog_color": [0.2, 0.15, 0.18],
        "fog_density": 0.018,
    },
    "night": {
        "sun_rotation_x": -30.0,
        "sun_rotation_y": 170.0,
        "sun_color": [0.18, 0.22, 0.38],
        "sun_intensity": 0.1,
        "ambient_color": [0.04, 0.04, 0.08],
        "fog_color": [0.04, 0.04, 0.08],
        "fog_density": 0.025,
    },
    "midnight": {
        "sun_rotation_x": -60.0,
        "sun_rotation_y": 170.0,
        "sun_color": [0.1, 0.12, 0.25],
        "sun_intensity": 0.05,
        "ambient_color": [0.02, 0.02, 0.05],
        "fog_color": [0.02, 0.02, 0.05],
        "fog_density": 0.035,
    },
}


# ---------------------------------------------------------------------------
# SCNE-01: Scene creation + async loading
# ---------------------------------------------------------------------------


def generate_scene_creation_script(
    scene_name: str = "NewScene",
    scene_setup: str = "DefaultGameObjects",
    loading_mode: str = "single",
    build_index: int = -1,
    namespace: str = "VeilBreakers.WorldSystems",
) -> str:
    """Generate C# editor script for scene creation and async loading.

    Creates a scene via ``EditorSceneManager.NewScene`` and provides a
    runtime helper for ``SceneManager.LoadSceneAsync`` with explicit
    ``LoadSceneMode``.

    Args:
        scene_name: Name of the scene to create.
        scene_setup: ``"DefaultGameObjects"`` or ``"EmptyScene"``.
        loading_mode: ``"single"`` or ``"additive"``.
        build_index: Build Settings index (-1 to skip).
        namespace: C# namespace for the generated class.

    Returns:
        Complete C# editor source string.
    """
    safe_name = _sanitize_cs_string(scene_name)
    safe_id = _sanitize_cs_identifier(scene_name)
    safe_ns = _sanitize_cs_identifier(namespace.replace(".", "_"))

    setup_enum = "NewSceneSetup.DefaultGameObjects"
    if scene_setup == "EmptyScene":
        setup_enum = "NewSceneSetup.EmptyScene"

    load_mode_enum = "LoadSceneMode.Single"
    if loading_mode == "additive":
        load_mode_enum = "LoadSceneMode.Additive"

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using UnityEditor.SceneManagement;")
    lines.append("using UnityEngine.SceneManagement;")
    lines.append("using System.IO;")
    lines.append("")
    lines.append(f"namespace {namespace}")
    lines.append("{")
    lines.append(f"    public static class VeilBreakers_SceneCreator_{safe_id}")
    lines.append("    {")
    lines.append(f'        [MenuItem("VeilBreakers/World/Create Scene ({safe_name})")]')
    lines.append("        public static void Execute()")
    lines.append("        {")
    lines.append(f'            string sceneName = "{safe_name}";')
    lines.append(f"            var scene = EditorSceneManager.NewScene({setup_enum}, NewSceneMode.Single);")
    lines.append("")
    lines.append('            string scenePath = "Assets/Scenes/" + sceneName + ".unity";')
    lines.append('            string dir = Path.GetDirectoryName(scenePath);')
    lines.append("            if (!Directory.Exists(dir)) Directory.CreateDirectory(dir);")
    lines.append("            EditorSceneManager.SaveScene(scene, scenePath);")
    lines.append("")

    if build_index >= 0:
        lines.append("            // Add to Build Settings")
        lines.append("            var scenes = new System.Collections.Generic.List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);")
        lines.append("            scenes.Add(new EditorBuildSettingsScene(scenePath, true));")
        lines.append("            EditorBuildSettings.scenes = scenes.ToArray();")
        lines.append("")

    lines.append(f'            Debug.Log("[VeilBreakers] Scene created: " + scenePath);')
    lines.append("")
    lines.append("            // Write result")
    lines.append('            string json = "{ \\"status\\": \\"ok\\", \\"scene_path\\": \\"" + scenePath + "\\" }";')
    lines.append('            File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("")
    lines.append("        /// <summary>Runtime async scene loader.</summary>")
    lines.append(f"        public static AsyncOperation LoadAsync(string sceneName, LoadSceneMode mode = {load_mode_enum})")
    lines.append("        {")
    lines.append("            AsyncOperation op = SceneManager.LoadSceneAsync(sceneName, mode);")
    lines.append("            return op;")
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SCNE-02: Scene transition system
# ---------------------------------------------------------------------------


def generate_scene_transition_script(
    fade_duration: float = 0.5,
    show_loading_screen: bool = True,
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate scene transition system (editor setup + runtime manager).

    The runtime ``VB_SceneTransitionManager`` is a singleton MonoBehaviour
    with ``DontDestroyOnLoad``.  It uses coroutine-based async loading with
    ``allowSceneActivation`` gating and a fade overlay.

    Supports the VeilBreakers flow:
    Bootstrap -> MainMenu -> CharacterSelect -> Overworld <-> Battle

    Args:
        fade_duration: Duration of fade in/out in seconds.
        show_loading_screen: Whether to show a loading progress bar.
        namespace: C# namespace.

    Returns:
        Tuple of ``(editor_cs, runtime_cs)``.
    """
    safe_ns = _sanitize_cs_identifier(namespace.replace(".", "_"))

    # ---- Runtime MonoBehaviour ----
    rt: list[str] = []
    rt.append("using UnityEngine;")
    rt.append("using UnityEngine.SceneManagement;")
    rt.append("using UnityEngine.UIElements;")
    rt.append("using System;")
    rt.append("using System.Collections;")
    rt.append("")
    rt.append(f"namespace {namespace}")
    rt.append("{")
    rt.append("    /// <summary>")
    rt.append("    /// Singleton scene transition manager with fade and loading screen.")
    rt.append("    /// Flow: Bootstrap -> MainMenu -> CharacterSelect -> Overworld <-> Battle")
    rt.append("    /// </summary>")
    rt.append("    public class VB_SceneTransitionManager : MonoBehaviour")
    rt.append("    {")
    rt.append("        public static VB_SceneTransitionManager Instance { get; private set; }")
    rt.append("")
    rt.append(f"        [SerializeField] private float fadeDuration = {fade_duration}f;")
    rt.append(f"        [SerializeField] private bool showLoadingScreen = {str(show_loading_screen).lower()};")
    rt.append("        [SerializeField] private CanvasGroup fadeOverlay;")
    rt.append("        [SerializeField] private GameObject loadingScreenRoot;")
    rt.append("        [SerializeField] private UnityEngine.UI.Slider progressBar;")
    rt.append("")
    rt.append("        public float LoadProgress { get; private set; }")
    rt.append("        public bool IsTransitioning { get; private set; }")
    rt.append("")
    rt.append("        public event Action<string> OnSceneLoadStarted;")
    rt.append("        public event Action<string> OnSceneLoadCompleted;")
    rt.append("")
    rt.append("        private void Awake()")
    rt.append("        {")
    rt.append("            if (Instance != null && Instance != this)")
    rt.append("            {")
    rt.append("                Destroy(gameObject);")
    rt.append("                return;")
    rt.append("            }")
    rt.append("            Instance = this;")
    rt.append("            DontDestroyOnLoad(gameObject);")
    rt.append("        }")
    rt.append("")
    rt.append("        /// <summary>Load a scene with fade transition.</summary>")
    rt.append("        public void TransitionToScene(string sceneName, LoadSceneMode mode = LoadSceneMode.Single)")
    rt.append("        {")
    rt.append("            if (IsTransitioning) return;")
    rt.append("            StartCoroutine(LoadSceneRoutine(sceneName, mode));")
    rt.append("        }")
    rt.append("")
    rt.append("        private IEnumerator LoadSceneRoutine(string sceneName, LoadSceneMode mode)")
    rt.append("        {")
    rt.append("            IsTransitioning = true;")
    rt.append("            LoadProgress = 0f;")
    rt.append("            OnSceneLoadStarted?.Invoke(sceneName);")
    rt.append("")
    rt.append("            // FadeOut")
    rt.append("            yield return StartCoroutine(FadeOut());")
    rt.append("")
    rt.append("            if (showLoadingScreen && loadingScreenRoot != null)")
    rt.append("                loadingScreenRoot.SetActive(true);")
    rt.append("")
    rt.append("            // Async load with activation gating")
    rt.append("            AsyncOperation op = SceneManager.LoadSceneAsync(sceneName, mode);")
    rt.append("            op.allowSceneActivation = false;")
    rt.append("")
    rt.append("            while (op.progress < 0.9f)")
    rt.append("            {")
    rt.append("                LoadProgress = Mathf.Clamp01(op.progress / 0.9f);")
    rt.append("                if (progressBar != null) progressBar.value = LoadProgress;")
    rt.append("                yield return null;")
    rt.append("            }")
    rt.append("")
    rt.append("            LoadProgress = 1f;")
    rt.append("            if (progressBar != null) progressBar.value = 1f;")
    rt.append("            yield return new WaitForSeconds(0.25f);")
    rt.append("")
    rt.append("            op.allowSceneActivation = true;")
    rt.append("            yield return op;")
    rt.append("")
    rt.append("            if (showLoadingScreen && loadingScreenRoot != null)")
    rt.append("                loadingScreenRoot.SetActive(false);")
    rt.append("")
    rt.append("            // FadeIn")
    rt.append("            yield return StartCoroutine(FadeIn());")
    rt.append("")
    rt.append("            IsTransitioning = false;")
    rt.append("            OnSceneLoadCompleted?.Invoke(sceneName);")
    rt.append("        }")
    rt.append("")
    rt.append("        private IEnumerator FadeOut()")
    rt.append("        {")
    rt.append("            if (fadeOverlay == null) yield break;")
    rt.append("            fadeOverlay.gameObject.SetActive(true);")
    rt.append("            float t = 0f;")
    rt.append("            while (t < fadeDuration)")
    rt.append("            {")
    rt.append("                t += Time.unscaledDeltaTime;")
    rt.append("                fadeOverlay.alpha = Mathf.Clamp01(t / fadeDuration);")
    rt.append("                yield return null;")
    rt.append("            }")
    rt.append("            fadeOverlay.alpha = 1f;")
    rt.append("        }")
    rt.append("")
    rt.append("        private IEnumerator FadeIn()")
    rt.append("        {")
    rt.append("            if (fadeOverlay == null) yield break;")
    rt.append("            float t = 0f;")
    rt.append("            while (t < fadeDuration)")
    rt.append("            {")
    rt.append("                t += Time.unscaledDeltaTime;")
    rt.append("                fadeOverlay.alpha = 1f - Mathf.Clamp01(t / fadeDuration);")
    rt.append("                yield return null;")
    rt.append("            }")
    rt.append("            fadeOverlay.alpha = 0f;")
    rt.append("            fadeOverlay.gameObject.SetActive(false);")
    rt.append("        }")
    rt.append("    }")
    rt.append("}")
    rt.append("")

    runtime_cs = "\n".join(rt)

    # ---- Editor script ----
    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append(f"namespace {namespace}")
    ed.append("{")
    ed.append("    public static class VeilBreakers_TransitionSetup")
    ed.append("    {")
    ed.append('        [MenuItem("VeilBreakers/World/Setup Scene Transition Manager")]')
    ed.append("        public static void Execute()")
    ed.append("        {")
    ed.append('            var existing = Object.FindFirstObjectByType<VB_SceneTransitionManager>();')
    ed.append("            if (existing != null)")
    ed.append("            {")
    ed.append('                Debug.LogWarning("[VeilBreakers] SceneTransitionManager already exists.");')
    ed.append("                Selection.activeGameObject = existing.gameObject;")
    ed.append("                return;")
    ed.append("            }")
    ed.append("")
    ed.append('            var go = new GameObject("[SceneTransitionManager]");')
    ed.append("            go.AddComponent<VB_SceneTransitionManager>();")
    ed.append("")
    ed.append("            // Create fade overlay Canvas")
    ed.append('            var canvasGo = new GameObject("FadeOverlay");')
    ed.append("            canvasGo.transform.SetParent(go.transform);")
    ed.append("            var canvas = canvasGo.AddComponent<Canvas>();")
    ed.append("            canvas.renderMode = RenderMode.ScreenSpaceOverlay;")
    ed.append("            canvas.sortingOrder = 9999;")
    ed.append("            var cg = canvasGo.AddComponent<CanvasGroup>();")
    ed.append("            cg.alpha = 0f;")
    ed.append("            cg.blocksRaycasts = false;")
    ed.append("")
    ed.append('            var imgGo = new GameObject("FadeImage");')
    ed.append("            imgGo.transform.SetParent(canvasGo.transform);")
    ed.append("            var img = imgGo.AddComponent<UnityEngine.UI.Image>();")
    ed.append("            img.color = Color.black;")
    ed.append("            var rt = img.rectTransform;")
    ed.append("            rt.anchorMin = Vector2.zero;")
    ed.append("            rt.anchorMax = Vector2.one;")
    ed.append("            rt.offsetMin = Vector2.zero;")
    ed.append("            rt.offsetMax = Vector2.zero;")
    ed.append("")
    ed.append("            // Wire serialized fields via SerializedObject")
    ed.append("            var mgr = go.GetComponent<VB_SceneTransitionManager>();")
    ed.append("            var so = new SerializedObject(mgr);")
    ed.append('            so.FindProperty("fadeOverlay").objectReferenceValue = cg;')
    ed.append("            so.ApplyModifiedProperties();")
    ed.append("")
    ed.append("            Selection.activeGameObject = go;")
    ed.append('            Debug.Log("[VeilBreakers] SceneTransitionManager created with fade overlay.");')
    ed.append("")
    ed.append('            string json = "{ \\"status\\": \\"ok\\", \\"object\\": \\"SceneTransitionManager\\" }";')
    ed.append('            System.IO.File.WriteAllText("Temp/vb_result.json", json);')
    ed.append("        }")
    ed.append("    }")
    ed.append("}")
    ed.append("")

    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# SCNE-03: Reflection probes + light probes
# ---------------------------------------------------------------------------


def generate_probe_setup_script(
    reflection_probe_count: int = 4,
    reflection_resolution: int = 256,
    probe_box_size: list[float] | None = None,
    light_probe_grid_spacing: float = 2.0,
    light_probe_grid_size: list[int] | None = None,
    namespace: str = "VeilBreakers.WorldSystems",
) -> str:
    """Generate C# editor script to set up reflection probes and light probes.

    Creates ``ReflectionProbe`` components with configurable mode, resolution,
    and box size.  Creates a ``LightProbeGroup`` with a programmatic grid of
    probe positions.

    Args:
        reflection_probe_count: Number of reflection probes to create.
        reflection_resolution: Resolution per probe face (64, 128, 256, 512, 1024).
        probe_box_size: Box size ``[x, y, z]`` for each reflection probe.
        light_probe_grid_spacing: Metres between light probes.
        light_probe_grid_size: Grid dimensions ``[x, y, z]`` in probe count.
        namespace: C# namespace.

    Returns:
        Complete C# editor source string.
    """
    if probe_box_size is None:
        probe_box_size = [10.0, 5.0, 10.0]
    if light_probe_grid_size is None:
        light_probe_grid_size = [5, 3, 5]

    bx, by, bz = probe_box_size[0], probe_box_size[1], probe_box_size[2]
    gx, gy, gz = light_probe_grid_size[0], light_probe_grid_size[1], light_probe_grid_size[2]

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Rendering;")
    lines.append("using UnityEditor;")
    lines.append("using System.Collections.Generic;")
    lines.append("")
    lines.append(f"namespace {namespace}")
    lines.append("{")
    lines.append("    public static class VeilBreakers_ProbeSetup")
    lines.append("    {")
    lines.append('        [MenuItem("VeilBreakers/World/Setup Probes")]')
    lines.append("        public static void Execute()")
    lines.append("        {")
    lines.append(f"            int probeCount = {reflection_probe_count};")
    lines.append(f"            int probeRes = {reflection_resolution};")
    lines.append(f"            Vector3 boxSize = new Vector3({bx}f, {by}f, {bz}f);")
    lines.append("")
    lines.append("            // Create reflection probes in a grid")
    lines.append("            for (int i = 0; i < probeCount; i++)")
    lines.append("            {")
    lines.append('                var go = new GameObject($"VB_ReflectionProbe_{i}");')
    lines.append("                go.transform.position = new Vector3(i * boxSize.x, boxSize.y * 0.5f, 0f);")
    lines.append("                ReflectionProbe probe = go.AddComponent<ReflectionProbe>();")
    lines.append("                probe.mode = ReflectionProbeMode.Baked;")
    lines.append("                probe.resolution = probeRes;")
    lines.append("                probe.size = boxSize;")
    lines.append("                probe.boxProjection = true;")
    lines.append("            }")
    lines.append("")
    lines.append("            // Create light probe group with programmatic grid positions")
    lines.append('            var lpgGo = new GameObject("VB_LightProbeGroup");')
    lines.append("            LightProbeGroup lpg = lpgGo.AddComponent<LightProbeGroup>();")
    lines.append("")
    lines.append(f"            float spacing = {light_probe_grid_spacing}f;")
    lines.append(f"            int gx = {gx}, gy = {gy}, gz = {gz};")
    lines.append("            var positions = new List<Vector3>();")
    lines.append("            for (int x = 0; x < gx; x++)")
    lines.append("                for (int y = 0; y < gy; y++)")
    lines.append("                    for (int z = 0; z < gz; z++)")
    lines.append("                        positions.Add(new Vector3(x * spacing, y * spacing, z * spacing));")
    lines.append("")
    lines.append("            lpg.probePositions = positions.ToArray();")
    lines.append("")
    lines.append('            Debug.Log($"[VeilBreakers] Created {probeCount} reflection probes and {positions.Count} light probes.");')
    lines.append("")
    lines.append('            string json = $"{{ \\"status\\": \\"ok\\", \\"reflection_probes\\": {probeCount}, \\"light_probes\\": {positions.Count} }}";')
    lines.append('            System.IO.File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SCNE-04: Occlusion culling setup
# ---------------------------------------------------------------------------


def generate_occlusion_setup_script(
    smallest_occluder: float = 5.0,
    smallest_hole: float = 0.25,
    backface_threshold: float = 100.0,
    namespace: str = "VeilBreakers.WorldSystems",
) -> str:
    """Generate C# editor script for occlusion culling setup.

    Marks selected objects with ``StaticEditorFlags.OccluderStatic`` or
    ``OccludeeStatic`` based on renderer bounds, then triggers
    ``StaticOcclusionCulling.Compute()``.

    Args:
        smallest_occluder: Minimum size for an object to be an occluder.
        smallest_hole: Smallest gap for visibility.
        backface_threshold: Threshold for back-face geometry.
        namespace: C# namespace.

    Returns:
        Complete C# editor source string.
    """
    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("")
    lines.append(f"namespace {namespace}")
    lines.append("{")
    lines.append("    public static class VeilBreakers_OcclusionSetup")
    lines.append("    {")
    lines.append('        [MenuItem("VeilBreakers/World/Setup Occlusion")]')
    lines.append("        public static void Execute()")
    lines.append("        {")
    lines.append(f"            float smallestOccluder = {smallest_occluder}f;")
    lines.append(f"            float smallestHole = {smallest_hole}f;")
    lines.append(f"            float backfaceThreshold = {backface_threshold}f;")
    lines.append("")
    lines.append("            // Configure occlusion settings")
    lines.append("            StaticOcclusionCulling.smallestOccluder = smallestOccluder;")
    lines.append("            StaticOcclusionCulling.smallestHole = smallestHole;")
    lines.append("            StaticOcclusionCulling.backfaceThreshold = backfaceThreshold;")
    lines.append("")
    lines.append("            int occluderCount = 0;")
    lines.append("            int occludeeCount = 0;")
    lines.append("")
    lines.append("            // Mark all renderers in scene")
    lines.append("            var renderers = Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None);")
    lines.append("            foreach (var r in renderers)")
    lines.append("            {")
    lines.append("                var go = r.gameObject;")
    lines.append("                var bounds = r.bounds;")
    lines.append("                float maxExtent = Mathf.Max(bounds.extents.x, bounds.extents.y, bounds.extents.z) * 2f;")
    lines.append("")
    lines.append("                StaticEditorFlags flags = GameObjectUtility.GetStaticEditorFlags(go);")
    lines.append("")
    lines.append("                if (maxExtent >= smallestOccluder)")
    lines.append("                {")
    lines.append("                    // Large objects are both occluders and occludees")
    lines.append("                    flags |= StaticEditorFlags.OccluderStatic | StaticEditorFlags.OccludeeStatic;")
    lines.append("                    GameObjectUtility.SetStaticEditorFlags(go, flags);")
    lines.append("                    occluderCount++;")
    lines.append("                }")
    lines.append("                else")
    lines.append("                {")
    lines.append("                    // Small objects are occludees only")
    lines.append("                    flags |= StaticEditorFlags.OccludeeStatic;")
    lines.append("                    GameObjectUtility.SetStaticEditorFlags(go, flags);")
    lines.append("                    occludeeCount++;")
    lines.append("                }")
    lines.append("            }")
    lines.append("")
    lines.append("            // Bake occlusion data")
    lines.append("            StaticOcclusionCulling.Compute();")
    lines.append("")
    lines.append('            Debug.Log($"[VeilBreakers] Occlusion setup: {occluderCount} occluders, {occludeeCount} occludees. Bake started.");')
    lines.append("")
    lines.append('            string json = $"{{ \\"status\\": \\"ok\\", \\"occluders\\": {occluderCount}, \\"occludees\\": {occludeeCount} }}";')
    lines.append('            System.IO.File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SCNE-05: HDR skybox + GI
# ---------------------------------------------------------------------------


def generate_environment_setup_script(
    skybox_shader: str = "Skybox/Procedural",
    ambient_mode: str = "Skybox",
    default_reflection_mode: str = "Skybox",
    enable_gi: bool = True,
    namespace: str = "VeilBreakers.WorldSystems",
) -> str:
    """Generate C# editor script for HDR skybox, ambient, and GI setup.

    Configures ``RenderSettings`` (skybox material, ambientMode,
    defaultReflectionMode).  Optionally triggers ``Lightmapping.BakeAsync()``
    for global illumination.

    Args:
        skybox_shader: Shader name for the skybox material.
        ambient_mode: ``"Skybox"``, ``"Trilight"``, or ``"Flat"``.
        default_reflection_mode: ``"Skybox"`` or ``"Custom"``.
        enable_gi: Whether to trigger GI baking.
        namespace: C# namespace.

    Returns:
        Complete C# editor source string.
    """
    safe_shader = _sanitize_cs_string(skybox_shader)

    ambient_enum = "AmbientMode.Skybox"
    if ambient_mode == "Trilight":
        ambient_enum = "AmbientMode.Trilight"
    elif ambient_mode == "Flat":
        ambient_enum = "AmbientMode.Flat"

    reflection_enum = "DefaultReflectionMode.Skybox"
    if default_reflection_mode == "Custom":
        reflection_enum = "DefaultReflectionMode.Custom"

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Rendering;")
    lines.append("using UnityEditor;")
    lines.append("")
    lines.append(f"namespace {namespace}")
    lines.append("{")
    lines.append("    public static class VeilBreakers_EnvironmentSetup")
    lines.append("    {")
    lines.append('        [MenuItem("VeilBreakers/World/Setup Environment")]')
    lines.append("        public static void Execute()")
    lines.append("        {")
    lines.append(f'            var skyboxMat = new Material(Shader.Find("{safe_shader}"));')
    lines.append('            skyboxMat.name = "VB_Skybox";')
    lines.append("")
    lines.append("            RenderSettings.skybox = skyboxMat;")
    lines.append(f"            RenderSettings.ambientMode = {ambient_enum};")
    lines.append(f"            RenderSettings.defaultReflectionMode = {reflection_enum};")
    lines.append("            RenderSettings.ambientIntensity = 1.0f;")
    lines.append("            RenderSettings.reflectionIntensity = 1.0f;")
    lines.append("")

    if enable_gi:
        lines.append("            // Trigger Global Illumination bake")
        lines.append("            Lightmapping.BakeAsync();")
        lines.append('            Debug.Log("[VeilBreakers] Environment configured. GI bake started.");')
    else:
        lines.append('            Debug.Log("[VeilBreakers] Environment configured. GI bake skipped.");')

    lines.append("")
    lines.append('            string json = "{ \\"status\\": \\"ok\\", \\"skybox_shader\\": \\"" +')
    lines.append(f'                "{safe_shader}" + "\\", \\"gi_baking\\": " +')
    lines.append(f'                "{str(enable_gi).lower()}" + " }}";')
    lines.append('            System.IO.File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SCNE-06: Terrain detail painting
# ---------------------------------------------------------------------------


def generate_terrain_detail_script(
    detail_prototypes: list[dict] | None = None,
    paint_density: int = 8,
    namespace: str = "VeilBreakers.WorldSystems",
) -> str:
    """Generate C# editor script for terrain detail/grass painting.

    Creates ``DetailPrototype`` array on ``TerrainData`` and paints density
    maps via ``SetDetailLayer``.

    Args:
        detail_prototypes: List of dicts, each with:
            - ``type``: ``"grass_texture"`` or ``"detail_mesh"``
            - ``texture_path`` or ``prefab_path``: Asset path
            - ``min_height``, ``max_height``: Height range
            - ``min_width``, ``max_width``: Width range
            - ``color``: ``[r, g, b]`` (optional, defaults to green)
        paint_density: Base density for SetDetailLayer (0-16).
        namespace: C# namespace.

    Returns:
        Complete C# editor source string.
    """
    if detail_prototypes is None:
        detail_prototypes = [
            {
                "type": "grass_texture",
                "texture_path": "Assets/Textures/Grass/grass_01.png",
                "min_height": 0.5,
                "max_height": 1.2,
                "min_width": 0.5,
                "max_width": 1.0,
                "color": [0.3, 0.5, 0.2],
            },
        ]

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("")
    lines.append(f"namespace {namespace}")
    lines.append("{")
    lines.append("    public static class VeilBreakers_TerrainDetail")
    lines.append("    {")
    lines.append('        [MenuItem("VeilBreakers/World/Paint Terrain Detail")]')
    lines.append("        public static void Execute()")
    lines.append("        {")
    lines.append("            var terrain = Terrain.activeTerrain;")
    lines.append("            if (terrain == null)")
    lines.append("            {")
    lines.append('                Debug.LogError("[VeilBreakers] No active terrain found.");')
    lines.append("                return;")
    lines.append("            }")
    lines.append("")
    lines.append("            TerrainData td = terrain.terrainData;")
    lines.append(f"            int protoCount = {len(detail_prototypes)};")
    lines.append("            DetailPrototype[] protos = new DetailPrototype[protoCount];")
    lines.append("")

    for i, proto in enumerate(detail_prototypes):
        ptype = proto.get("type", "grass_texture")
        min_h = proto.get("min_height", 0.5)
        max_h = proto.get("max_height", 1.2)
        min_w = proto.get("min_width", 0.5)
        max_w = proto.get("max_width", 1.0)
        color = proto.get("color", [0.3, 0.5, 0.2])

        lines.append(f"            protos[{i}] = new DetailPrototype();")
        lines.append(f"            protos[{i}].minHeight = {min_h}f;")
        lines.append(f"            protos[{i}].maxHeight = {max_h}f;")
        lines.append(f"            protos[{i}].minWidth = {min_w}f;")
        lines.append(f"            protos[{i}].maxWidth = {max_w}f;")
        lines.append(f"            protos[{i}].healthyColor = new Color({color[0]}f, {color[1]}f, {color[2]}f);")
        lines.append(f"            protos[{i}].dryColor = new Color({color[0] * 0.7}f, {color[1] * 0.7}f, {color[2] * 0.7}f);")

        if ptype == "grass_texture":
            tex_path = _sanitize_cs_string(proto.get("texture_path", ""))
            lines.append(f'            protos[{i}].prototypeTexture = AssetDatabase.LoadAssetAtPath<Texture2D>("{tex_path}");')
            lines.append(f"            protos[{i}].renderMode = DetailRenderMode.GrassBillboard;")
        else:
            prefab_path = _sanitize_cs_string(proto.get("prefab_path", ""))
            lines.append(f'            protos[{i}].prototype = AssetDatabase.LoadAssetAtPath<GameObject>("{prefab_path}");')
            lines.append(f"            protos[{i}].renderMode = DetailRenderMode.VertexLit;")
            lines.append(f"            protos[{i}].usePrototypeMesh = true;")
        lines.append("")

    lines.append("            td.detailPrototypes = protos;")
    lines.append("")
    lines.append("            // Paint density maps for each layer")
    lines.append("            int detailRes = td.detailResolution;")
    lines.append("            for (int layerIdx = 0; layerIdx < protoCount; layerIdx++)")
    lines.append("            {")
    lines.append("                int[,] densityMap = new int[detailRes, detailRes];")
    lines.append("                for (int y = 0; y < detailRes; y++)")
    lines.append("                    for (int x = 0; x < detailRes; x++)")
    lines.append(f"                        densityMap[y, x] = {paint_density};")
    lines.append("                td.SetDetailLayer(0, 0, layerIdx, densityMap);")
    lines.append("            }")
    lines.append("")
    lines.append('            Debug.Log($"[VeilBreakers] Painted {protoCount} detail layers at density {0}.");')
    lines.append("            terrain.Flush();")
    lines.append("")
    lines.append('            string json = $"{{ \\"status\\": \\"ok\\", \\"detail_layers\\": {protoCount} }}";')
    lines.append('            System.IO.File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TWO-01: Tilemap + Rule Tiles
# ---------------------------------------------------------------------------


def generate_tilemap_setup_script(
    grid_cell_size: list[float] | None = None,
    tile_entries: list[dict] | None = None,
    rule_tile_name: str = "",
    rule_tile_rules: list[dict] | None = None,
    namespace: str = "VeilBreakers.WorldSystems",
) -> str:
    """Generate C# editor script for Tilemap creation and tile placement.

    Creates a ``Tilemap`` on a ``Grid``, places tiles via ``SetTile``.
    Optionally creates a ``RuleTile`` ScriptableObject with auto-tiling
    rules.

    Args:
        grid_cell_size: Grid cell size ``[x, y, z]``.
        tile_entries: List of dicts with ``x``, ``y``, ``tile_asset_path``.
        rule_tile_name: If non-empty, create a RuleTile with this name.
        rule_tile_rules: List of rule dicts for auto-tiling.
        namespace: C# namespace.

    Returns:
        Complete C# editor source string.
    """
    if grid_cell_size is None:
        grid_cell_size = [1.0, 1.0, 0.0]
    if tile_entries is None:
        tile_entries = []

    cx, cy, cz = grid_cell_size[0], grid_cell_size[1], grid_cell_size[2]

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Tilemaps;")
    lines.append("using UnityEditor;")
    lines.append("")
    lines.append(f"namespace {namespace}")
    lines.append("{")
    lines.append("    public static class VeilBreakers_TilemapSetup")
    lines.append("    {")
    lines.append('        [MenuItem("VeilBreakers/World/Setup Tilemap")]')
    lines.append("        public static void Execute()")
    lines.append("        {")
    lines.append("            // Create Grid")
    lines.append('            var gridGo = new GameObject("VB_Grid");')
    lines.append("            var grid = gridGo.AddComponent<Grid>();")
    lines.append(f"            grid.cellSize = new Vector3({cx}f, {cy}f, {cz}f);")
    lines.append("")
    lines.append("            // Create Tilemap")
    lines.append('            var tilemapGo = new GameObject("VB_Tilemap");')
    lines.append("            tilemapGo.transform.SetParent(gridGo.transform);")
    lines.append("            Tilemap tilemap = tilemapGo.AddComponent<Tilemap>();")
    lines.append("            tilemapGo.AddComponent<TilemapRenderer>();")
    lines.append("")

    # Place individual tiles
    if tile_entries:
        lines.append("            // Place tiles")
        for entry in tile_entries:
            tx = entry.get("x", 0)
            ty = entry.get("y", 0)
            tile_path = _sanitize_cs_string(entry.get("tile_asset_path", ""))
            lines.append(f'            var tile_{tx}_{ty} = AssetDatabase.LoadAssetAtPath<TileBase>("{tile_path}");')
            lines.append(f"            tilemap.SetTile(new Vector3Int({tx}, {ty}, 0), tile_{tx}_{ty});")
        lines.append("")

    # Optional RuleTile creation
    if rule_tile_name:
        safe_rt_name = _sanitize_cs_string(rule_tile_name)
        safe_rt_id = _sanitize_cs_identifier(rule_tile_name)
        lines.append("            // Create RuleTile")
        lines.append("            var ruleTile = ScriptableObject.CreateInstance<RuleTile>();")
        lines.append(f'            ruleTile.name = "{safe_rt_name}";')

        if rule_tile_rules:
            lines.append("            ruleTile.m_TilingRules = new System.Collections.Generic.List<RuleTile.TilingRule>();")
            for _ri, rule in enumerate(rule_tile_rules):
                lines.append("            {")
                lines.append("                var rule = new RuleTile.TilingRule();")
                output = rule.get("output", "single")
                if output == "random":
                    lines.append("                rule.m_Output = RuleTile.TilingRuleOutput.OutputSprite.Random;")
                else:
                    lines.append("                rule.m_Output = RuleTile.TilingRuleOutput.OutputSprite.Single;")
                lines.append("                ruleTile.m_TilingRules.Add(rule);")
                lines.append("            }")

        lines.append(f'            AssetDatabase.CreateAsset(ruleTile, "Assets/Tiles/{safe_rt_id}_RuleTile.asset");')
        lines.append("")

    lines.append("            tilemap.RefreshAllTiles();")
    lines.append("")
    lines.append('            Debug.Log("[VeilBreakers] Tilemap created and tiles placed.");')
    lines.append("")
    lines.append('            string json = "{ \\"status\\": \\"ok\\", \\"tilemap\\": \\"VB_Tilemap\\" }";')
    lines.append('            System.IO.File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TWO-02: 2D Physics configuration
# ---------------------------------------------------------------------------


def generate_2d_physics_script(
    gravity: list[float] | None = None,
    collider_type: str = "box",
    body_type: str = "Dynamic",
    joint_type: str = "",
    joint_params: dict | None = None,
    namespace: str = "VeilBreakers.WorldSystems",
) -> str:
    """Generate C# editor script for 2D physics configuration.

    Configures ``Physics2D.gravity``, adds ``Rigidbody2D`` with the specified
    body type and a collider (``BoxCollider2D``, ``CircleCollider2D``, or
    ``CompositeCollider2D``).  Optionally adds a 2D joint
    (``HingeJoint2D``, ``SpringJoint2D``, ``DistanceJoint2D``).

    Args:
        gravity: 2D gravity ``[x, y]``.
        collider_type: ``"box"``, ``"circle"``, or ``"composite"``.
        body_type: ``"Dynamic"``, ``"Kinematic"``, or ``"Static"``.
        joint_type: Optional: ``"hinge"``, ``"spring"``, or ``"distance"``.
        joint_params: Optional dict with joint-specific parameters.
        namespace: C# namespace.

    Returns:
        Complete C# editor source string.
    """
    if gravity is None:
        gravity = [0.0, -9.81]
    if joint_params is None:
        joint_params = {}

    gx, gy = gravity[0], gravity[1]

    body_type_enum = "RigidbodyType2D.Dynamic"
    if body_type == "Kinematic":
        body_type_enum = "RigidbodyType2D.Kinematic"
    elif body_type == "Static":
        body_type_enum = "RigidbodyType2D.Static"

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("")
    lines.append(f"namespace {namespace}")
    lines.append("{")
    lines.append("    public static class VeilBreakers_2DPhysicsSetup")
    lines.append("    {")
    lines.append('        [MenuItem("VeilBreakers/World/Setup 2D Physics")]')
    lines.append("        public static void Execute()")
    lines.append("        {")
    lines.append(f"            Physics2D.gravity = new Vector2({gx}f, {gy}f);")
    lines.append("")
    lines.append("            // Apply to selected objects (or create demo)")
    lines.append("            GameObject target = Selection.activeGameObject;")
    lines.append("            if (target == null)")
    lines.append("            {")
    lines.append('                target = new GameObject("VB_2DPhysicsBody");')
    lines.append("            }")
    lines.append("")
    lines.append("            // Rigidbody2D")
    lines.append("            Rigidbody2D rb = target.GetComponent<Rigidbody2D>();")
    lines.append("            if (rb == null) rb = target.AddComponent<Rigidbody2D>();")
    lines.append(f"            rb.bodyType = {body_type_enum};")
    lines.append("")

    # Collider
    if collider_type == "box":
        lines.append("            // BoxCollider2D")
        lines.append("            BoxCollider2D boxCol = target.GetComponent<BoxCollider2D>();")
        lines.append("            if (boxCol == null) boxCol = target.AddComponent<BoxCollider2D>();")
    elif collider_type == "circle":
        lines.append("            // CircleCollider2D")
        lines.append("            CircleCollider2D circleCol = target.GetComponent<CircleCollider2D>();")
        lines.append("            if (circleCol == null) circleCol = target.AddComponent<CircleCollider2D>();")
    elif collider_type == "composite":
        lines.append("            // CompositeCollider2D (requires Rigidbody2D)")
        lines.append("            CompositeCollider2D compCol = target.GetComponent<CompositeCollider2D>();")
        lines.append("            if (compCol == null) compCol = target.AddComponent<CompositeCollider2D>();")
        lines.append("            // Add a BoxCollider2D as composite geometry source")
        lines.append("            BoxCollider2D srcCol = target.GetComponent<BoxCollider2D>();")
        lines.append("            if (srcCol == null) srcCol = target.AddComponent<BoxCollider2D>();")
        lines.append("            srcCol.usedByComposite = true;")

    lines.append("")

    # Optional joint
    if joint_type == "hinge":
        anchor = joint_params.get("anchor", [0, 0])
        lines.append("            // HingeJoint2D")
        lines.append("            HingeJoint2D hinge = target.AddComponent<HingeJoint2D>();")
        lines.append(f"            hinge.anchor = new Vector2({anchor[0]}f, {anchor[1]}f);")
        use_motor = joint_params.get("use_motor", False)
        if use_motor:
            motor_speed = joint_params.get("motor_speed", 100.0)
            motor_torque = joint_params.get("motor_torque", 50.0)
            lines.append("            hinge.useMotor = true;")
            lines.append(f"            hinge.motor = new JointMotor2D {{ motorSpeed = {motor_speed}f, maxMotorTorque = {motor_torque}f }};")
    elif joint_type == "spring":
        distance = joint_params.get("distance", 2.0)
        frequency = joint_params.get("frequency", 4.0)
        damping = joint_params.get("damping_ratio", 0.5)
        lines.append("            // SpringJoint2D")
        lines.append("            SpringJoint2D spring = target.AddComponent<SpringJoint2D>();")
        lines.append(f"            spring.distance = {distance}f;")
        lines.append(f"            spring.frequency = {frequency}f;")
        lines.append(f"            spring.dampingRatio = {damping}f;")
    elif joint_type == "distance":
        max_dist = joint_params.get("max_distance", 5.0)
        lines.append("            // DistanceJoint2D")
        lines.append("            DistanceJoint2D distJoint = target.AddComponent<DistanceJoint2D>();")
        lines.append(f"            distJoint.maxDistanceOnly = true;")
        lines.append(f"            distJoint.distance = {max_dist}f;")

    lines.append("")
    lines.append("            Selection.activeGameObject = target;")
    lines.append('            Debug.Log("[VeilBreakers] 2D Physics configured.");')
    lines.append("")
    lines.append('            string json = "{ \\"status\\": \\"ok\\", \\"body_type\\": \\"" +')
    lines.append(f'                "{body_type}" + "\\", \\"collider\\": \\"" +')
    lines.append(f'                "{collider_type}" + "\\" }}";')
    lines.append('            System.IO.File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WORLD-08: Time-of-day lighting presets
# ---------------------------------------------------------------------------


def generate_time_of_day_preset_script(
    preset_name: str = "noon",
    custom_overrides: dict | None = None,
    apply_fog: bool = True,
    namespace: str = "VeilBreakers.WorldSystems",
) -> str:
    """Generate C# editor script to apply a time-of-day lighting preset.

    Uses the ``_WORLD_TIME_PRESETS`` dictionary with 8 presets (dawn, morning,
    noon, afternoon, dusk, evening, night, midnight).  Applies sun rotation,
    colour, intensity, ambient light, fog settings, and skybox tint.

    Args:
        preset_name: One of the 8 preset names.
        custom_overrides: Optional dict to override preset values (keys
            match preset dict: sun_color, sun_intensity, ambient_color,
            fog_color, fog_density).
        apply_fog: Whether to enable and configure fog.
        namespace: C# namespace.

    Returns:
        Complete C# editor source string.
    """
    preset = _WORLD_TIME_PRESETS.get(preset_name, _WORLD_TIME_PRESETS["noon"])

    # Apply custom overrides
    if custom_overrides:
        preset = {**preset, **custom_overrides}

    sun_rx = preset["sun_rotation_x"]
    sun_ry = preset["sun_rotation_y"]
    sun_c = preset["sun_color"]
    sun_i = preset["sun_intensity"]
    amb_c = preset["ambient_color"]
    fog_c = preset["fog_color"]
    fog_d = preset["fog_density"]

    safe_preset = _sanitize_cs_string(preset_name)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Rendering;")
    lines.append("using UnityEditor;")
    lines.append("")
    lines.append(f"namespace {namespace}")
    lines.append("{")
    lines.append("    public static class VeilBreakers_TimeOfDay")
    lines.append("    {")
    lines.append(f'        [MenuItem("VeilBreakers/World/Apply Time of Day ({safe_preset})")]')
    lines.append("        public static void Execute()")
    lines.append("        {")
    lines.append("            // Find or create directional light (sun)")
    lines.append("            Light sun = null;")
    lines.append("            var lights = Object.FindObjectsByType<Light>(FindObjectsSortMode.None);")
    lines.append("            foreach (var l in lights)")
    lines.append("            {")
    lines.append("                if (l.type == LightType.Directional)")
    lines.append("                {")
    lines.append("                    sun = l;")
    lines.append("                    break;")
    lines.append("                }")
    lines.append("            }")
    lines.append("")
    lines.append("            if (sun == null)")
    lines.append("            {")
    lines.append('                var sunGo = new GameObject("Directional Light");')
    lines.append("                sun = sunGo.AddComponent<Light>();")
    lines.append("                sun.type = LightType.Directional;")
    lines.append("            }")
    lines.append("")
    lines.append(f"            sun.transform.rotation = Quaternion.Euler({sun_rx}f, {sun_ry}f, 0f);")
    lines.append(f"            sun.color = new Color({sun_c[0]}f, {sun_c[1]}f, {sun_c[2]}f);")
    lines.append(f"            sun.intensity = {sun_i}f;")
    lines.append("")
    lines.append("            // Ambient lighting")
    lines.append("            RenderSettings.ambientMode = AmbientMode.Flat;")
    lines.append(f"            RenderSettings.ambientLight = new Color({amb_c[0]}f, {amb_c[1]}f, {amb_c[2]}f);")
    lines.append("")

    if apply_fog:
        lines.append("            // Fog settings")
        lines.append("            RenderSettings.fog = true;")
        lines.append("            RenderSettings.fogMode = FogMode.ExponentialSquared;")
        lines.append(f"            RenderSettings.fogColor = new Color({fog_c[0]}f, {fog_c[1]}f, {fog_c[2]}f);")
        lines.append(f"            RenderSettings.fogDensity = {fog_d}f;")
    else:
        lines.append("            RenderSettings.fog = false;")

    lines.append("")
    lines.append("            // Skybox tint -- adjust skybox material if present")
    lines.append("            if (RenderSettings.skybox != null)")
    lines.append("            {")
    lines.append('                if (RenderSettings.skybox.HasProperty("_Tint"))')
    lines.append(f'                    RenderSettings.skybox.SetColor("_Tint", new Color({amb_c[0]}f, {amb_c[1]}f, {amb_c[2]}f));')
    lines.append('                if (RenderSettings.skybox.HasProperty("_SunSize"))')
    lines.append(f'                    RenderSettings.skybox.SetFloat("_SunSize", {0.04 if sun_i > 0.3 else 0.0}f);')
    lines.append("            }")
    lines.append("")
    lines.append(f'            Debug.Log("[VeilBreakers] Time-of-day preset applied: {safe_preset}");')
    lines.append("")
    lines.append(f'            string json = "{{ \\"status\\": \\"ok\\", \\"preset\\": \\"{safe_preset}\\" }}";')
    lines.append('            System.IO.File.WriteAllText("Temp/vb_result.json", json);')
    lines.append("        }")
    lines.append("    }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "generate_scene_creation_script",
    "generate_scene_transition_script",
    "generate_probe_setup_script",
    "generate_occlusion_setup_script",
    "generate_environment_setup_script",
    "generate_terrain_detail_script",
    "generate_tilemap_setup_script",
    "generate_2d_physics_script",
    "generate_time_of_day_preset_script",
]
