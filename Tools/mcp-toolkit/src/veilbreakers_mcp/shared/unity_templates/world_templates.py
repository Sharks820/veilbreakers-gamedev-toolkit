"""World and scene management C# template generators for Unity automation.

Each function returns a complete C# source string (or tuple for multi-file
generators) that can be written to Unity project directories.  Editor scripts
go to ``Assets/Editor/Generated/World/`` and register under the
``VeilBreakers/World/...`` MenuItem menu.  Runtime MonoBehaviours go to
``Assets/Scripts/Runtime/WorldSystems/``.

Exports:
    generate_scene_creation_script          -- SCNE-01: scene creation + async loading
    generate_scene_transition_script        -- SCNE-02: scene transition system (returns tuple)
    generate_probe_setup_script             -- SCNE-03: reflection probes + light probes
    generate_occlusion_setup_script         -- SCNE-04: occlusion culling setup
    generate_environment_setup_script       -- SCNE-05: HDR skybox + GI
    generate_terrain_detail_script          -- SCNE-06: terrain detail painting
    generate_tilemap_setup_script           -- TWO-01: tilemap + rule tiles
    generate_2d_physics_script              -- TWO-02: 2D physics configuration
    generate_time_of_day_preset_script      -- WORLD-08: 8 time-of-day presets
    generate_fast_travel_script             -- RPG-02: waypoint discovery + teleport
    generate_puzzle_mechanics_script        -- RPG-04: 4 puzzle subclasses
    generate_trap_system_script             -- RPG-06: 5 trap subclasses
    generate_spatial_loot_script            -- RPG-07: room-based loot placement
    generate_weather_system_script          -- RPG-09: weather state machine + particle lerp
    generate_day_night_cycle_script         -- RPG-10: continuous time + lighting presets
    generate_npc_placement_script           -- RPG-11: SO data + placement manager
    generate_dungeon_lighting_script        -- RPG-12: torch sconces + atmospheric fog
    generate_terrain_building_blend_script  -- RPG-13: vertex color + decal + depression

Note: ``generate_scene_transition_script`` returns a **tuple** of two strings
(editor_cs, runtime_cs).  RPG generators return tuples (editor_cs, runtime_cs)
or triples (so_cs, runtime_cs, editor_cs) for NPC placement.
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
# C# reserved words (needed by RPG generators for _safe_namespace)
# ---------------------------------------------------------------------------

_CS_RESERVED = frozenset({
    "abstract", "as", "base", "bool", "break", "byte", "case", "catch", "char",
    "checked", "class", "const", "continue", "decimal", "default", "delegate",
    "do", "double", "else", "enum", "event", "explicit", "extern", "false",
    "finally", "fixed", "float", "for", "foreach", "goto", "if", "implicit",
    "in", "int", "interface", "internal", "is", "lock", "long", "namespace",
    "new", "null", "object", "operator", "out", "override", "params", "private",
    "protected", "public", "readonly", "ref", "return", "sbyte", "sealed",
    "short", "sizeof", "stackalloc", "static", "string", "struct", "switch",
    "this", "throw", "true", "try", "typeof", "uint", "ulong", "unchecked",
    "unsafe", "ushort", "using", "virtual", "void", "volatile", "while",
})


def _safe_namespace(ns: str) -> str:
    """Sanitize a C# namespace to prevent code injection."""
    sanitized = re.sub(r"[^a-zA-Z0-9_.]", "", ns)
    sanitized = re.sub(r"\.{2,}", ".", sanitized).strip(".")
    if not sanitized:
        return "Generated"
    segments = sanitized.split(".")
    fixed: list[str] = []
    for seg in segments:
        if not seg:
            continue
        if seg[0].isdigit():
            seg = f"_{seg}"
        if seg in _CS_RESERVED:
            seg = f"@{seg}"
        fixed.append(seg)
    return ".".join(fixed) or "Generated"


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
    lines.append(f"namespace {_safe_namespace(namespace)}")
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
    rt.append(f"namespace {_safe_namespace(namespace)}")
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
    ed.append(f"namespace {_safe_namespace(namespace)}")
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
    lines.append(f"namespace {_safe_namespace(namespace)}")
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
    lines.append(f"namespace {_safe_namespace(namespace)}")
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
    lines.append(f"namespace {_safe_namespace(namespace)}")
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
    lines.append(f"namespace {_safe_namespace(namespace)}")
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
    lines.append(f"namespace {_safe_namespace(namespace)}")
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
    lines.append(f"namespace {_safe_namespace(namespace)}")
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
    lines.append(f"namespace {_safe_namespace(namespace)}")
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


# ===========================================================================
# RPG World System Generators (RPG-02, 04, 06, 07, 09, 10, 11, 12, 13)
# ===========================================================================


# ---------------------------------------------------------------------------
# RPG-02: Fast travel / waypoint system
# ---------------------------------------------------------------------------


def generate_fast_travel_script(
    waypoint_prefab_path: str = "Prefabs/Waypoint",
    teleport_fade_duration: float = 0.5,
    save_key: str = "discoveredWaypoints",
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate C# for a fast travel waypoint system.

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    ns = _safe_namespace(namespace)
    safe_key = _sanitize_cs_string(save_key)

    # ----- Runtime: VB_WaypointManager -----
    rt: list[str] = []
    rt.append("using System;")
    rt.append("using System.Collections;")
    rt.append("using System.Collections.Generic;")
    rt.append("using UnityEngine;")
    rt.append("using UnityEngine.Events;")
    rt.append("using UnityEngine.SceneManagement;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    rt.append("    [Serializable]")
    rt.append("    public class WaypointSaveData")
    rt.append("    {")
    rt.append("        public List<string> discoveredWaypoints = new List<string>();")
    rt.append("    }")
    rt.append("")
    rt.append("    /// <summary>")
    rt.append("    /// Fast travel waypoint manager. Discovers waypoints on trigger,")
    rt.append("    /// teleports player with loading transition, persists via JsonUtility.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public class VB_WaypointManager : MonoBehaviour")
    rt.append("    {")
    rt.append("        public static VB_WaypointManager Instance { get; private set; }")
    rt.append("")
    rt.append("        [Header(\"Waypoint Settings\")]")
    rt.append("        [SerializeField] private float _teleportFadeDuration = " + str(teleport_fade_duration) + "f;")
    rt.append("        [SerializeField] private string _saveKey = \"" + safe_key + "\";")
    rt.append("")
    rt.append("        [Header(\"Events\")]")
    rt.append("        public UnityEvent<string> OnWaypointDiscovered;")
    rt.append("        public UnityEvent<string> OnTeleportStarted;")
    rt.append("        public UnityEvent<string> OnTeleportCompleted;")
    rt.append("")
    rt.append("        private List<string> _discoveredWaypoints = new List<string>();")
    rt.append("        private bool _isTeleporting;")
    rt.append("")
    rt.append("        public IReadOnlyList<string> DiscoveredWaypoints => _discoveredWaypoints;")
    rt.append("")
    rt.append("        private void Awake()")
    rt.append("        {")
    rt.append("            if (Instance != null) { Destroy(gameObject); return; }")
    rt.append("            Instance = this;")
    rt.append("            DontDestroyOnLoad(gameObject);")
    rt.append("            LoadDiscoveredWaypoints();")
    rt.append("        }")
    rt.append("")
    rt.append("        private void OnTriggerEnter(Collider other)")
    rt.append("        {")
    rt.append("            if (!other.CompareTag(\"Player\")) return;")
    rt.append("            string waypointId = gameObject.name;")
    rt.append("            if (!_discoveredWaypoints.Contains(waypointId))")
    rt.append("            {")
    rt.append("                _discoveredWaypoints.Add(waypointId);")
    rt.append("                SaveDiscoveredWaypoints();")
    rt.append("                OnWaypointDiscovered?.Invoke(waypointId);")
    rt.append("            }")
    rt.append("        }")
    rt.append("")
    rt.append("        public void DiscoverWaypoint(string waypointId)")
    rt.append("        {")
    rt.append("            if (string.IsNullOrEmpty(waypointId)) return;")
    rt.append("            if (!_discoveredWaypoints.Contains(waypointId))")
    rt.append("            {")
    rt.append("                _discoveredWaypoints.Add(waypointId);")
    rt.append("                SaveDiscoveredWaypoints();")
    rt.append("                OnWaypointDiscovered?.Invoke(waypointId);")
    rt.append("            }")
    rt.append("        }")
    rt.append("")
    rt.append("        public bool IsDiscovered(string waypointId)")
    rt.append("        {")
    rt.append("            return _discoveredWaypoints.Contains(waypointId);")
    rt.append("        }")
    rt.append("")
    rt.append("        public void TeleportTo(string waypointId, string sceneName = null, Vector3 position = default)")
    rt.append("        {")
    rt.append("            if (_isTeleporting) return;")
    rt.append("            if (!_discoveredWaypoints.Contains(waypointId)) return;")
    rt.append("            StartCoroutine(TeleportRoutine(waypointId, sceneName, position));")
    rt.append("        }")
    rt.append("")
    rt.append("        private IEnumerator TeleportRoutine(string waypointId, string sceneName, Vector3 position)")
    rt.append("        {")
    rt.append("            _isTeleporting = true;")
    rt.append("            OnTeleportStarted?.Invoke(waypointId);")
    rt.append("            yield return new WaitForSeconds(_teleportFadeDuration);")
    rt.append("")
    rt.append("            if (!string.IsNullOrEmpty(sceneName))")
    rt.append("            {")
    rt.append("                AsyncOperation op = SceneManager.LoadSceneAsync(sceneName);")
    rt.append("                op.allowSceneActivation = false;")
    rt.append("                while (op.progress < 0.9f) yield return null;")
    rt.append("                op.allowSceneActivation = true;")
    rt.append("                yield return op;")
    rt.append("            }")
    rt.append("")
    rt.append("            GameObject player = GameObject.FindWithTag(\"Player\");")
    rt.append("            if (player != null && position != default)")
    rt.append("                player.transform.position = position;")
    rt.append("")
    rt.append("            yield return new WaitForSeconds(_teleportFadeDuration);")
    rt.append("            _isTeleporting = false;")
    rt.append("            OnTeleportCompleted?.Invoke(waypointId);")
    rt.append("        }")
    rt.append("")
    rt.append("        private void SaveDiscoveredWaypoints()")
    rt.append("        {")
    rt.append("            WaypointSaveData data = new WaypointSaveData();")
    rt.append("            data.discoveredWaypoints = new List<string>(_discoveredWaypoints);")
    rt.append("            string json = JsonUtility.ToJson(data);")
    rt.append("            PlayerPrefs.SetString(_saveKey, json);")
    rt.append("            PlayerPrefs.Save();")
    rt.append("        }")
    rt.append("")
    rt.append("        private void LoadDiscoveredWaypoints()")
    rt.append("        {")
    rt.append("            string json = PlayerPrefs.GetString(_saveKey, \"\");")
    rt.append("            if (!string.IsNullOrEmpty(json))")
    rt.append("            {")
    rt.append("                WaypointSaveData data = JsonUtility.FromJson<WaypointSaveData>(json);")
    rt.append("                if (data != null && data.discoveredWaypoints != null)")
    rt.append("                    _discoveredWaypoints = data.discoveredWaypoints;")
    rt.append("            }")
    rt.append("        }")
    rt.append("    }")
    rt.append("}")
    runtime_cs = "\n".join(rt)

    # ----- Editor -----
    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_FastTravelSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Setup Fast Travel\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        GameObject go = new GameObject(\"VB_WaypointManager\");")
    ed.append("        go.AddComponent<" + ns + ".VB_WaypointManager>();")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("        Debug.Log(\"[VeilBreakers] Fast travel waypoint manager created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# RPG-04: Environmental puzzle mechanics
# ---------------------------------------------------------------------------


def generate_puzzle_mechanics_script(
    puzzle_types: Optional[list[str]] = None,
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate C# for environmental puzzle mechanics.

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    if puzzle_types is None:
        puzzle_types = ["lever_sequence", "pressure_plate", "key_lock", "light_beam"]
    ns = _safe_namespace(namespace)

    rt: list[str] = []
    rt.append("using System;")
    rt.append("using System.Collections.Generic;")
    rt.append("using UnityEngine;")
    rt.append("using UnityEngine.Events;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    # PuzzleMechanic abstract base
    rt.append("    /// <summary>")
    rt.append("    /// Abstract base class for all environmental puzzle mechanics.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public abstract class PuzzleMechanic : MonoBehaviour")
    rt.append("    {")
    rt.append("        [Header(\"Puzzle Base\")]")
    rt.append("        [SerializeField] protected string _puzzleId;")
    rt.append("        [SerializeField] protected bool _isReusable;")
    rt.append("        public UnityEvent OnSolved;")
    rt.append("        public UnityEvent OnReset;")
    rt.append("        public abstract bool IsSolved { get; }")
    rt.append("        public abstract void ResetPuzzle();")
    rt.append("        protected void NotifySolved() { OnSolved?.Invoke(); }")
    rt.append("    }")
    rt.append("")

    if "lever_sequence" in puzzle_types:
        rt.append("    public class LeverSequencePuzzle : PuzzleMechanic")
        rt.append("    {")
        rt.append("        [SerializeField] private int[] _correctSequence;")
        rt.append("        private List<int> _currentSequence = new List<int>();")
        rt.append("        private bool _solved;")
        rt.append("        public override bool IsSolved => _solved;")
        rt.append("        public void ActivateLever(int leverIndex)")
        rt.append("        {")
        rt.append("            if (_solved) return;")
        rt.append("            _currentSequence.Add(leverIndex);")
        rt.append("            if (_currentSequence.Count == _correctSequence.Length)")
        rt.append("            {")
        rt.append("                bool correct = true;")
        rt.append("                for (int i = 0; i < _correctSequence.Length; i++)")
        rt.append("                    if (_currentSequence[i] != _correctSequence[i]) { correct = false; break; }")
        rt.append("                if (correct) { _solved = true; NotifySolved(); }")
        rt.append("                else _currentSequence.Clear();")
        rt.append("            }")
        rt.append("        }")
        rt.append("        public override void ResetPuzzle() { _solved = false; _currentSequence.Clear(); OnReset?.Invoke(); }")
        rt.append("    }")
        rt.append("")

    if "pressure_plate" in puzzle_types:
        rt.append("    public class PressurePlatePuzzle : PuzzleMechanic")
        rt.append("    {")
        rt.append("        [SerializeField] private float _requiredWeight = 50f;")
        rt.append("        [SerializeField] private float _tolerance = 5f;")
        rt.append("        private float _currentWeight;")
        rt.append("        private bool _solved;")
        rt.append("        public override bool IsSolved => _solved;")
        rt.append("        private void OnTriggerEnter(Collider other)")
        rt.append("        {")
        rt.append("            Rigidbody rb = other.attachedRigidbody;")
        rt.append("            if (rb != null) _currentWeight += rb.mass;")
        rt.append("            CheckSolved();")
        rt.append("        }")
        rt.append("        private void OnTriggerExit(Collider other)")
        rt.append("        {")
        rt.append("            Rigidbody rb = other.attachedRigidbody;")
        rt.append("            if (rb != null) _currentWeight -= rb.mass;")
        rt.append("        }")
        rt.append("        private void CheckSolved()")
        rt.append("        {")
        rt.append("            if (_solved) return;")
        rt.append("            if (Mathf.Abs(_currentWeight - _requiredWeight) <= _tolerance)")
        rt.append("            { _solved = true; NotifySolved(); }")
        rt.append("        }")
        rt.append("        public override void ResetPuzzle() { _solved = false; _currentWeight = 0f; OnReset?.Invoke(); }")
        rt.append("    }")
        rt.append("")

    if "key_lock" in puzzle_types:
        rt.append("    public class KeyLockPuzzle : PuzzleMechanic")
        rt.append("    {")
        rt.append("        [SerializeField] private string _requiredKeyId;")
        rt.append("        private bool _solved;")
        rt.append("        public override bool IsSolved => _solved;")
        rt.append("        public string RequiredKeyId => _requiredKeyId;")
        rt.append("        public bool TryUnlock(string keyId)")
        rt.append("        {")
        rt.append("            if (_solved) return true;")
        rt.append("            if (keyId == _requiredKeyId) { _solved = true; NotifySolved(); return true; }")
        rt.append("            return false;")
        rt.append("        }")
        rt.append("        public override void ResetPuzzle() { _solved = false; OnReset?.Invoke(); }")
        rt.append("    }")
        rt.append("")

    if "light_beam" in puzzle_types:
        rt.append("    public class LightBeamPuzzle : PuzzleMechanic")
        rt.append("    {")
        rt.append("        [SerializeField] private Transform _lightSource;")
        rt.append("        [SerializeField] private Transform _target;")
        rt.append("        [SerializeField] private float _alignmentThreshold = 5f;")
        rt.append("        [SerializeField] private LineRenderer _beamRenderer;")
        rt.append("        private bool _solved;")
        rt.append("        public override bool IsSolved => _solved;")
        rt.append("        private void Update()")
        rt.append("        {")
        rt.append("            if (_solved || _lightSource == null || _target == null) return;")
        rt.append("            Vector3 dirToTarget = (_target.position - _lightSource.position).normalized;")
        rt.append("            float angle = Vector3.Angle(_lightSource.forward, dirToTarget);")
        rt.append("            if (_beamRenderer != null)")
        rt.append("            {")
        rt.append("                _beamRenderer.SetPosition(0, _lightSource.position);")
        rt.append("                _beamRenderer.SetPosition(1, _lightSource.position + _lightSource.forward * 20f);")
        rt.append("            }")
        rt.append("            if (angle <= _alignmentThreshold) { _solved = true; NotifySolved(); }")
        rt.append("        }")
        rt.append("        public override void ResetPuzzle() { _solved = false; OnReset?.Invoke(); }")
        rt.append("    }")
        rt.append("")

    rt.append("}")
    runtime_cs = "\n".join(rt)

    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_PuzzleSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Create Puzzle\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        GameObject go = new GameObject(\"VB_Puzzle\");")
    ed.append("        go.AddComponent<" + ns + ".LeverSequencePuzzle>();")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("        Debug.Log(\"[VeilBreakers] Puzzle mechanic created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# RPG-06: Dungeon trap system
# ---------------------------------------------------------------------------


def generate_trap_system_script(
    trap_types: Optional[list[str]] = None,
    base_damage: float = 25.0,
    cooldown: float = 3.0,
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate C# for dungeon trap mechanics.

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    if trap_types is None:
        trap_types = ["pressure_plate", "dart_wall", "spike_pit", "poison_gas", "swinging_blade"]
    ns = _safe_namespace(namespace)

    rt: list[str] = []
    rt.append("using System;")
    rt.append("using System.Collections;")
    rt.append("using UnityEngine;")
    rt.append("using UnityEngine.Events;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    # TrapBase abstract
    rt.append("    /// <summary>")
    rt.append("    /// Abstract base class for all dungeon traps.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public abstract class TrapBase : MonoBehaviour")
    rt.append("    {")
    rt.append("        [Header(\"Trap Base\")]")
    rt.append("        [SerializeField] protected float _damage = " + str(base_damage) + "f;")
    rt.append("        [SerializeField] protected float _cooldown = " + str(cooldown) + "f;")
    rt.append("        [SerializeField] protected bool _isArmed = true;")
    rt.append("        public UnityEvent OnActivated;")
    rt.append("        public UnityEvent OnReset;")
    rt.append("        protected bool _onCooldown;")
    rt.append("        public float Damage => _damage;")
    rt.append("        public float Cooldown => _cooldown;")
    rt.append("        public bool IsArmed => _isArmed;")
    rt.append("        public abstract void Activate();")
    rt.append("        public abstract void Reset();")
    rt.append("        protected void ApplyDamage(GameObject target)")
    rt.append("        {")
    rt.append("            Debug.Log($\"[Trap] {name} dealt {_damage} damage to {target.name}\");")
    rt.append("        }")
    rt.append("        protected IEnumerator CooldownRoutine()")
    rt.append("        {")
    rt.append("            _onCooldown = true;")
    rt.append("            yield return new WaitForSeconds(_cooldown);")
    rt.append("            _onCooldown = false;")
    rt.append("            _isArmed = true;")
    rt.append("        }")
    rt.append("    }")
    rt.append("")

    if "pressure_plate" in trap_types:
        rt.append("    public class PressurePlateTrap : TrapBase")
        rt.append("    {")
        rt.append("        private void OnTriggerEnter(Collider other)")
        rt.append("        {")
        rt.append("            if (!_isArmed || _onCooldown) return;")
        rt.append("            if (other.CompareTag(\"Player\")) { Activate(); ApplyDamage(other.gameObject); }")
        rt.append("        }")
        rt.append("        public override void Activate() { _isArmed = false; OnActivated?.Invoke(); StartCoroutine(CooldownRoutine()); }")
        rt.append("        public override void Reset() { _isArmed = true; _onCooldown = false; OnReset?.Invoke(); }")
        rt.append("    }")
        rt.append("")

    if "dart_wall" in trap_types:
        rt.append("    public class DartWallTrap : TrapBase")
        rt.append("    {")
        rt.append("        [SerializeField] private GameObject _dartPrefab;")
        rt.append("        [SerializeField] private Transform _spawnPoint;")
        rt.append("        [SerializeField] private float _dartSpeed = 15f;")
        rt.append("        public override void Activate()")
        rt.append("        {")
        rt.append("            if (!_isArmed || _onCooldown) return;")
        rt.append("            _isArmed = false;")
        rt.append("            if (_dartPrefab != null && _spawnPoint != null)")
        rt.append("            {")
        rt.append("                GameObject dart = Instantiate(_dartPrefab, _spawnPoint.position, _spawnPoint.rotation);")
        rt.append("                Rigidbody rb = dart.GetComponent<Rigidbody>();")
        rt.append("                if (rb != null) rb.velocity = _spawnPoint.forward * _dartSpeed;")
        rt.append("                Destroy(dart, 5f);")
        rt.append("            }")
        rt.append("            OnActivated?.Invoke();")
        rt.append("            StartCoroutine(CooldownRoutine());")
        rt.append("        }")
        rt.append("        public override void Reset() { _isArmed = true; _onCooldown = false; OnReset?.Invoke(); }")
        rt.append("    }")
        rt.append("")

    if "spike_pit" in trap_types:
        rt.append("    public class SpikePitTrap : TrapBase")
        rt.append("    {")
        rt.append("        [SerializeField] private Transform _coverTransform;")
        rt.append("        [SerializeField] private float _fallDepth = 3f;")
        rt.append("        private void OnTriggerEnter(Collider other)")
        rt.append("        {")
        rt.append("            if (!_isArmed || _onCooldown) return;")
        rt.append("            if (other.CompareTag(\"Player\")) { Activate(); ApplyDamage(other.gameObject); }")
        rt.append("        }")
        rt.append("        public override void Activate()")
        rt.append("        {")
        rt.append("            _isArmed = false;")
        rt.append("            if (_coverTransform != null) _coverTransform.gameObject.SetActive(false);")
        rt.append("            OnActivated?.Invoke();")
        rt.append("            StartCoroutine(CooldownRoutine());")
        rt.append("        }")
        rt.append("        public override void Reset()")
        rt.append("        {")
        rt.append("            _isArmed = true; _onCooldown = false;")
        rt.append("            if (_coverTransform != null) _coverTransform.gameObject.SetActive(true);")
        rt.append("            OnReset?.Invoke();")
        rt.append("        }")
        rt.append("    }")
        rt.append("")

    if "poison_gas" in trap_types:
        rt.append("    public class PoisonGasTrap : TrapBase")
        rt.append("    {")
        rt.append("        [SerializeField] private ParticleSystem _gasParticles;")
        rt.append("        [SerializeField] private float _gasDuration = 5f;")
        rt.append("        [SerializeField] private float _tickInterval = 0.5f;")
        rt.append("        [SerializeField] private float _damageRadius = 3f;")
        rt.append("        public override void Activate()")
        rt.append("        {")
        rt.append("            if (!_isArmed || _onCooldown) return;")
        rt.append("            _isArmed = false;")
        rt.append("            if (_gasParticles != null) _gasParticles.Play();")
        rt.append("            StartCoroutine(GasDamageRoutine());")
        rt.append("            OnActivated?.Invoke();")
        rt.append("        }")
        rt.append("        private IEnumerator GasDamageRoutine()")
        rt.append("        {")
        rt.append("            float elapsed = 0f;")
        rt.append("            while (elapsed < _gasDuration)")
        rt.append("            {")
        rt.append("                Collider[] hits = Physics.OverlapSphere(transform.position, _damageRadius);")
        rt.append("                foreach (Collider hit in hits)")
        rt.append("                    if (hit.CompareTag(\"Player\")) ApplyDamage(hit.gameObject);")
        rt.append("                yield return new WaitForSeconds(_tickInterval);")
        rt.append("                elapsed += _tickInterval;")
        rt.append("            }")
        rt.append("            if (_gasParticles != null) _gasParticles.Stop();")
        rt.append("            StartCoroutine(CooldownRoutine());")
        rt.append("        }")
        rt.append("        public override void Reset() { _isArmed = true; _onCooldown = false; if (_gasParticles != null) _gasParticles.Stop(); OnReset?.Invoke(); }")
        rt.append("    }")
        rt.append("")

    if "swinging_blade" in trap_types:
        rt.append("    public class SwingingBladeTrap : TrapBase")
        rt.append("    {")
        rt.append("        [SerializeField] private float _swingAngle = 60f;")
        rt.append("        [SerializeField] private float _swingSpeed = 2f;")
        rt.append("        [SerializeField] private Transform _bladePivot;")
        rt.append("        private bool _isSwinging;")
        rt.append("        public override void Activate() { _isSwinging = true; OnActivated?.Invoke(); }")
        rt.append("        private void Update()")
        rt.append("        {")
        rt.append("            if (!_isSwinging || _bladePivot == null) return;")
        rt.append("            float angle = _swingAngle * Mathf.Sin(Time.time * _swingSpeed);")
        rt.append("            _bladePivot.localRotation = Quaternion.Euler(0f, 0f, angle);")
        rt.append("        }")
        rt.append("        private void OnTriggerEnter(Collider other)")
        rt.append("        {")
        rt.append("            if (!_isSwinging) return;")
        rt.append("            if (other.CompareTag(\"Player\")) ApplyDamage(other.gameObject);")
        rt.append("        }")
        rt.append("        public override void Reset()")
        rt.append("        {")
        rt.append("            _isSwinging = false; _isArmed = true; _onCooldown = false;")
        rt.append("            if (_bladePivot != null) _bladePivot.localRotation = Quaternion.identity;")
        rt.append("            OnReset?.Invoke();")
        rt.append("        }")
        rt.append("    }")
        rt.append("")

    rt.append("}")
    runtime_cs = "\n".join(rt)

    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_TrapSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Create Trap\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        GameObject go = new GameObject(\"VB_Trap\");")
    ed.append("        go.AddComponent<" + ns + ".PressurePlateTrap>();")
    ed.append("        BoxCollider col = go.AddComponent<BoxCollider>();")
    ed.append("        col.isTrigger = true;")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("        Debug.Log(\"[VeilBreakers] Trap created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# RPG-07: Spatial loot placement
# ---------------------------------------------------------------------------


def generate_spatial_loot_script(
    chest_prefab_path: str = "Prefabs/TreasureChest",
    loot_table_so_path: str = "Data/LootTables",
    room_loot_density: float = 0.3,
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate C# for spatial loot placement system.

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    ns = _safe_namespace(namespace)

    rt: list[str] = []
    rt.append("using System;")
    rt.append("using System.Collections.Generic;")
    rt.append("using UnityEngine;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    rt.append("    [Serializable]")
    rt.append("    public class LootEntry")
    rt.append("    {")
    rt.append("        public string itemId;")
    rt.append("        public float weight = 1f;")
    rt.append("        public int minCount = 1;")
    rt.append("        public int maxCount = 1;")
    rt.append("    }")
    rt.append("")
    rt.append("    [CreateAssetMenu(fileName = \"NewRoomLootTable\", menuName = \"VeilBreakers/Loot/Room Loot Table\")]")
    rt.append("    public class VB_RoomLootTable : ScriptableObject")
    rt.append("    {")
    rt.append("        public string roomType;")
    rt.append("        public LootEntry[] entries;")
    rt.append("        public int minDrops = 1;")
    rt.append("        public int maxDrops = 3;")
    rt.append("    }")
    rt.append("")
    rt.append("    /// <summary>")
    rt.append("    /// Manages treasure chest positions and room-based loot distribution.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public class VB_SpatialLootManager : MonoBehaviour")
    rt.append("    {")
    rt.append("        [Header(\"Chest Configuration\")]")
    rt.append("        [SerializeField] private GameObject _chestPrefab;")
    rt.append("        [SerializeField] private float _roomLootDensity = " + str(room_loot_density) + "f;")
    rt.append("        [Header(\"Loot Tables\")]")
    rt.append("        [SerializeField] private VB_RoomLootTable[] _lootTables;")
    rt.append("        [Header(\"Treasure Rooms\")]")
    rt.append("        [SerializeField] private string _treasureRoomTag = \"TreasureRoom\";")
    rt.append("        private List<GameObject> _spawnedChests = new List<GameObject>();")
    rt.append("")
    rt.append("        private void Start() { SpawnChestsAtMarkers(); }")
    rt.append("")
    rt.append("        public void SpawnChestsAtMarkers()")
    rt.append("        {")
    rt.append("            foreach (Transform child in transform)")
    rt.append("            {")
    rt.append("                if (_chestPrefab == null) continue;")
    rt.append("                GameObject chest = Instantiate(_chestPrefab, child.position, child.rotation);")
    rt.append("                _spawnedChests.Add(chest);")
    rt.append("            }")
    rt.append("        }")
    rt.append("")
    rt.append("        public LootEntry SelectLoot(string roomType)")
    rt.append("        {")
    rt.append("            VB_RoomLootTable table = FindTableForRoom(roomType);")
    rt.append("            if (table == null || table.entries.Length == 0) return null;")
    rt.append("            float totalWeight = 0f;")
    rt.append("            foreach (LootEntry entry in table.entries) totalWeight += entry.weight;")
    rt.append("            float roll = UnityEngine.Random.Range(0f, totalWeight);")
    rt.append("            float cumulative = 0f;")
    rt.append("            foreach (LootEntry entry in table.entries)")
    rt.append("            {")
    rt.append("                cumulative += entry.weight;")
    rt.append("                if (roll <= cumulative) return entry;")
    rt.append("            }")
    rt.append("            return table.entries[table.entries.Length - 1];")
    rt.append("        }")
    rt.append("")
    rt.append("        public bool IsTreasureRoom(GameObject room)")
    rt.append("        {")
    rt.append("            return room.CompareTag(_treasureRoomTag) || room.name.Contains(\"Treasure\");")
    rt.append("        }")
    rt.append("")
    rt.append("        private VB_RoomLootTable FindTableForRoom(string roomType)")
    rt.append("        {")
    rt.append("            if (_lootTables == null) return null;")
    rt.append("            foreach (VB_RoomLootTable table in _lootTables)")
    rt.append("                if (table.roomType == roomType) return table;")
    rt.append("            return null;")
    rt.append("        }")
    rt.append("    }")
    rt.append("}")
    runtime_cs = "\n".join(rt)

    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_SpatialLootSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Setup Spatial Loot\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        GameObject go = new GameObject(\"VB_SpatialLootManager\");")
    ed.append("        go.AddComponent<" + ns + ".VB_SpatialLootManager>();")
    ed.append("        for (int i = 0; i < 3; i++)")
    ed.append("        {")
    ed.append("            GameObject marker = new GameObject($\"ChestMarker_{i}\");")
    ed.append("            marker.transform.SetParent(go.transform);")
    ed.append("            marker.transform.localPosition = new Vector3(i * 3f, 0f, 0f);")
    ed.append("        }")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("        Debug.Log(\"[VeilBreakers] Spatial loot manager created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# RPG-09: Weather system
# ---------------------------------------------------------------------------


def generate_weather_system_script(
    weather_states: Optional[list[str]] = None,
    transition_duration: float = 3.0,
    default_state: str = "Clear",
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate C# for a weather state machine with particle-based transitions.

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    if weather_states is None:
        weather_states = ["Clear", "Rain", "Snow", "Fog", "Storm"]
    ns = _safe_namespace(namespace)

    rt: list[str] = []
    rt.append("using System;")
    rt.append("using System.Collections;")
    rt.append("using UnityEngine;")
    rt.append("using UnityEngine.Events;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    # WeatherState enum
    rt.append("    public enum WeatherState")
    rt.append("    {")
    for i, state in enumerate(weather_states):
        safe_state = _sanitize_cs_identifier(state)
        comma = "," if i < len(weather_states) - 1 else ""
        rt.append("        " + safe_state + comma)
    rt.append("    }")
    rt.append("")
    # WeatherManager
    rt.append("    /// <summary>")
    rt.append("    /// Weather manager with smooth coroutine-based transitions.")
    rt.append("    /// Uses ParticleSystem emission rate lerp for smooth weather changes.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public class VB_WeatherManager : MonoBehaviour")
    rt.append("    {")
    rt.append("        public static VB_WeatherManager Instance { get; private set; }")
    rt.append("        [Header(\"Weather Configuration\")]")
    rt.append("        [SerializeField] private float _transitionDuration = " + str(transition_duration) + "f;")
    rt.append("        [SerializeField] private WeatherState _defaultState = WeatherState." + _sanitize_cs_identifier(default_state) + ";")
    rt.append("        [Header(\"Particle Systems\")]")
    for state in weather_states:
        safe = _sanitize_cs_identifier(state)
        if safe != "Clear":
            rt.append("        [SerializeField] private ParticleSystem _" + safe.lower() + "Particles;")
    rt.append("        [Header(\"Fog Settings\")]")
    rt.append("        [SerializeField] private float _clearFogDensity = 0.001f;")
    rt.append("        [SerializeField] private float _foggyFogDensity = 0.05f;")
    rt.append("        [SerializeField] private Color _clearFogColor = new Color(0.7f, 0.8f, 0.9f);")
    rt.append("        [SerializeField] private Color _stormFogColor = new Color(0.3f, 0.3f, 0.35f);")
    rt.append("        [Header(\"Events\")]")
    rt.append("        public UnityEvent<WeatherState> OnWeatherChanged;")
    rt.append("        private WeatherState _currentWeather;")
    rt.append("        private Coroutine _transitionCoroutine;")
    rt.append("        public WeatherState CurrentWeather => _currentWeather;")
    rt.append("")
    rt.append("        private void Awake()")
    rt.append("        {")
    rt.append("            if (Instance != null) { Destroy(gameObject); return; }")
    rt.append("            Instance = this;")
    rt.append("            _currentWeather = _defaultState;")
    rt.append("        }")
    rt.append("")
    rt.append("        public void TransitionTo(WeatherState target)")
    rt.append("        {")
    rt.append("            if (target == _currentWeather) return;")
    rt.append("            if (_transitionCoroutine != null) StopCoroutine(_transitionCoroutine);")
    rt.append("            _transitionCoroutine = StartCoroutine(WeatherTransitionRoutine(target));")
    rt.append("        }")
    rt.append("")
    rt.append("        private IEnumerator WeatherTransitionRoutine(WeatherState target)")
    rt.append("        {")
    rt.append("            float elapsed = 0f;")
    rt.append("            ParticleSystem currentPS = GetParticleSystem(_currentWeather);")
    rt.append("            ParticleSystem targetPS = GetParticleSystem(target);")
    rt.append("            float currentRate = currentPS != null ? GetEmissionRate(currentPS) : 0f;")
    rt.append("            float targetRate = targetPS != null ? GetMaxEmissionRate(target) : 0f;")
    rt.append("            float startFog = RenderSettings.fogDensity;")
    rt.append("            float endFog = GetFogDensity(target);")
    rt.append("            Color startFogColor = RenderSettings.fogColor;")
    rt.append("            Color endFogColor = GetFogColor(target);")
    rt.append("")
    rt.append("            if (targetPS != null && !targetPS.isPlaying)")
    rt.append("            {")
    rt.append("                var emission = targetPS.emission;")
    rt.append("                emission.rateOverTime = 0f;")
    rt.append("                targetPS.Play();")
    rt.append("            }")
    rt.append("")
    rt.append("            while (elapsed < _transitionDuration)")
    rt.append("            {")
    rt.append("                float t = elapsed / _transitionDuration;")
    rt.append("                if (currentPS != null) { var emission = currentPS.emission; emission.rateOverTime = Mathf.Lerp(currentRate, 0f, t); }")
    rt.append("                if (targetPS != null) { var emission = targetPS.emission; emission.rateOverTime = Mathf.Lerp(0f, targetRate, t); }")
    rt.append("                RenderSettings.fogDensity = Mathf.Lerp(startFog, endFog, t);")
    rt.append("                RenderSettings.fogColor = Color.Lerp(startFogColor, endFogColor, t);")
    rt.append("                elapsed += Time.deltaTime;")
    rt.append("                yield return null;")
    rt.append("            }")
    rt.append("")
    rt.append("            if (currentPS != null) currentPS.Stop();")
    rt.append("            if (targetPS != null) { var emission = targetPS.emission; emission.rateOverTime = targetRate; }")
    rt.append("            RenderSettings.fogDensity = endFog;")
    rt.append("            RenderSettings.fogColor = endFogColor;")
    rt.append("            _currentWeather = target;")
    rt.append("            OnWeatherChanged?.Invoke(target);")
    rt.append("            _transitionCoroutine = null;")
    rt.append("        }")
    rt.append("")
    rt.append("        private ParticleSystem GetParticleSystem(WeatherState state)")
    rt.append("        {")
    rt.append("            switch (state)")
    rt.append("            {")
    for state_name in weather_states:
        safe = _sanitize_cs_identifier(state_name)
        if safe == "Clear":
            rt.append("                case WeatherState.Clear: return null;")
        else:
            rt.append("                case WeatherState." + safe + ": return _" + safe.lower() + "Particles;")
    rt.append("                default: return null;")
    rt.append("            }")
    rt.append("        }")
    rt.append("        private float GetEmissionRate(ParticleSystem ps) { var emission = ps.emission; return emission.rateOverTime.constant; }")
    rt.append("        private float GetMaxEmissionRate(WeatherState state)")
    rt.append("        {")
    rt.append("            switch (state) { case WeatherState.Rain: return 500f; case WeatherState.Snow: return 200f; case WeatherState.Fog: return 50f; case WeatherState.Storm: return 800f; default: return 0f; }")
    rt.append("        }")
    rt.append("        private float GetFogDensity(WeatherState state)")
    rt.append("        {")
    rt.append("            switch (state) { case WeatherState.Clear: return _clearFogDensity; case WeatherState.Fog: return _foggyFogDensity; case WeatherState.Storm: return _foggyFogDensity * 0.7f; default: return _clearFogDensity * 2f; }")
    rt.append("        }")
    rt.append("        private Color GetFogColor(WeatherState state)")
    rt.append("        {")
    rt.append("            switch (state) { case WeatherState.Storm: return _stormFogColor; default: return _clearFogColor; }")
    rt.append("        }")
    rt.append("    }")
    rt.append("}")
    runtime_cs = "\n".join(rt)

    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_WeatherSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Create Weather System\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        GameObject go = new GameObject(\"VB_WeatherManager\");")
    ed.append("        go.AddComponent<" + ns + ".VB_WeatherManager>();")
    ed.append("        string[] weatherTypes = { \"Rain\", \"Snow\", \"Fog\", \"Storm\" };")
    ed.append("        foreach (string wt in weatherTypes)")
    ed.append("        {")
    ed.append("            GameObject psGo = new GameObject($\"{wt}Particles\");")
    ed.append("            psGo.transform.SetParent(go.transform);")
    ed.append("            psGo.AddComponent<ParticleSystem>().Stop();")
    ed.append("        }")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("        Debug.Log(\"[VeilBreakers] Weather system created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# RPG-10: Day/night cycle
# ---------------------------------------------------------------------------


def generate_day_night_cycle_script(
    day_duration_minutes: float = 10.0,
    start_hour: float = 8.0,
    time_presets: Optional[list[str]] = None,
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate C# for a continuous day/night cycle with lighting presets.

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    if time_presets is None:
        time_presets = ["Dawn", "Morning", "Noon", "Afternoon", "Dusk", "Evening", "Night", "Midnight"]
    ns = _safe_namespace(namespace)

    rt: list[str] = []
    rt.append("using System;")
    rt.append("using System.Collections;")
    rt.append("using UnityEngine;")
    rt.append("using UnityEngine.Events;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    rt.append("    [Serializable]")
    rt.append("    public class TimeOfDayPreset")
    rt.append("    {")
    rt.append("        public string name;")
    rt.append("        public float hour;")
    rt.append("        public float sunIntensity = 1f;")
    rt.append("        public Color sunColor = Color.white;")
    rt.append("        public float sunAngle = 45f;")
    rt.append("        public Color ambientLight = new Color(0.2f, 0.2f, 0.25f);")
    rt.append("        public float fogDensity = 0.002f;")
    rt.append("        public Color fogColor = new Color(0.7f, 0.8f, 0.9f);")
    rt.append("    }")
    rt.append("")
    rt.append("    /// <summary>")
    rt.append("    /// Continuous day/night cycle with lighting preset transitions,")
    rt.append("    /// NPC schedule callbacks, and enemy behavior shift events.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public class VB_DayNightCycleManager : MonoBehaviour")
    rt.append("    {")
    rt.append("        public static VB_DayNightCycleManager Instance { get; private set; }")
    rt.append("        [Header(\"Time Settings\")]")
    rt.append("        [SerializeField] private float _dayDurationMinutes = " + str(day_duration_minutes) + "f;")
    rt.append("        [SerializeField] private float _startHour = " + str(start_hour) + "f;")
    rt.append("        [SerializeField] private bool _isPaused;")
    rt.append("        [Header(\"Lighting\")]")
    rt.append("        [SerializeField] private Light _directionalLight;")
    rt.append("        [SerializeField] private TimeOfDayPreset[] _presets;")
    rt.append("        [Header(\"Events\")]")
    rt.append("        public UnityEvent<float> OnTimeChanged;")
    rt.append("        public UnityEvent<bool> OnNightfall;")
    rt.append("        public UnityEvent<bool> OnDaybreak;")
    rt.append("        private float _timeOfDay;")
    rt.append("        private bool _wasNight;")
    rt.append("        public float CurrentHour => _timeOfDay;")
    rt.append("        public float NormalizedTime => _timeOfDay / 24f;")
    rt.append("        public bool IsNight => _timeOfDay >= 20f || _timeOfDay < 6f;")
    rt.append("")
    rt.append("        private void Awake()")
    rt.append("        {")
    rt.append("            if (Instance != null) { Destroy(gameObject); return; }")
    rt.append("            Instance = this;")
    rt.append("            _timeOfDay = _startHour;")
    rt.append("            _wasNight = IsNight;")
    rt.append("            InitializeDefaultPresets();")
    rt.append("        }")
    rt.append("")
    rt.append("        private void Update()")
    rt.append("        {")
    rt.append("            if (_isPaused) return;")
    rt.append("            float hoursPerSecond = 24f / (_dayDurationMinutes * 60f);")
    rt.append("            _timeOfDay += hoursPerSecond * Time.deltaTime;")
    rt.append("            if (_timeOfDay >= 24f) _timeOfDay -= 24f;")
    rt.append("            UpdateLighting();")
    rt.append("            OnTimeChanged?.Invoke(_timeOfDay);")
    rt.append("            bool isNightNow = IsNight;")
    rt.append("            if (isNightNow && !_wasNight) OnNightfall?.Invoke(true);")
    rt.append("            else if (!isNightNow && _wasNight) OnDaybreak?.Invoke(true);")
    rt.append("            _wasNight = isNightNow;")
    rt.append("        }")
    rt.append("")
    rt.append("        public void SetTime(float hour) { _timeOfDay = Mathf.Repeat(hour, 24f); UpdateLighting(); OnTimeChanged?.Invoke(_timeOfDay); }")
    rt.append("        public void PauseTime(bool pause) { _isPaused = pause; }")
    rt.append("")
    rt.append("        private void UpdateLighting()")
    rt.append("        {")
    rt.append("            if (_presets == null || _presets.Length < 2 || _directionalLight == null) return;")
    rt.append("            TimeOfDayPreset prev = _presets[_presets.Length - 1];")
    rt.append("            TimeOfDayPreset next = _presets[0];")
    rt.append("            for (int i = 0; i < _presets.Length; i++)")
    rt.append("            {")
    rt.append("                if (_presets[i].hour <= _timeOfDay) prev = _presets[i];")
    rt.append("                if (_presets[i].hour > _timeOfDay) { next = _presets[i]; break; }")
    rt.append("            }")
    rt.append("            float range = next.hour - prev.hour;")
    rt.append("            if (range <= 0f) range += 24f;")
    rt.append("            float offset = _timeOfDay - prev.hour;")
    rt.append("            if (offset < 0f) offset += 24f;")
    rt.append("            float t = range > 0f ? offset / range : 0f;")
    rt.append("            _directionalLight.intensity = Mathf.Lerp(prev.sunIntensity, next.sunIntensity, t);")
    rt.append("            _directionalLight.color = Color.Lerp(prev.sunColor, next.sunColor, t);")
    rt.append("            float angle = Mathf.Lerp(prev.sunAngle, next.sunAngle, t);")
    rt.append("            _directionalLight.transform.rotation = Quaternion.Euler(angle, -30f, 0f);")
    rt.append("            RenderSettings.ambientLight = Color.Lerp(prev.ambientLight, next.ambientLight, t);")
    rt.append("            RenderSettings.fogDensity = Mathf.Lerp(prev.fogDensity, next.fogDensity, t);")
    rt.append("            RenderSettings.fogColor = Color.Lerp(prev.fogColor, next.fogColor, t);")
    rt.append("        }")
    rt.append("")
    rt.append("        private void InitializeDefaultPresets()")
    rt.append("        {")
    rt.append("            if (_presets != null && _presets.Length > 0) return;")
    rt.append("            _presets = new TimeOfDayPreset[]")
    rt.append("            {")
    preset_data = [
        ("Dawn", 5.0, 0.3, "1.0f, 0.6f, 0.3f", 10, "0.15f, 0.12f, 0.18f", 0.008, "0.8f, 0.6f, 0.5f"),
        ("Morning", 7.0, 0.7, "1.0f, 0.9f, 0.8f", 30, "0.2f, 0.2f, 0.22f", 0.003, "0.7f, 0.8f, 0.9f"),
        ("Noon", 12.0, 1.2, "1.0f, 1.0f, 0.95f", 75, "0.3f, 0.3f, 0.32f", 0.001, "0.8f, 0.85f, 0.95f"),
        ("Afternoon", 15.0, 1.0, "1.0f, 0.95f, 0.85f", 55, "0.25f, 0.25f, 0.28f", 0.002, "0.75f, 0.8f, 0.9f"),
        ("Dusk", 18.0, 0.4, "1.0f, 0.5f, 0.2f", 15, "0.18f, 0.1f, 0.15f", 0.006, "0.9f, 0.5f, 0.3f"),
        ("Evening", 20.0, 0.15, "0.3f, 0.3f, 0.5f", 5, "0.08f, 0.08f, 0.12f", 0.004, "0.2f, 0.2f, 0.3f"),
        ("Night", 22.0, 0.05, "0.2f, 0.2f, 0.4f", -10, "0.03f, 0.03f, 0.06f", 0.003, "0.1f, 0.1f, 0.15f"),
        ("Midnight", 0.0, 0.02, "0.15f, 0.15f, 0.3f", -20, "0.02f, 0.02f, 0.04f", 0.005, "0.05f, 0.05f, 0.1f"),
    ]
    for name, hour, intensity, sun_col, angle, amb, fog_d, fog_c in preset_data:
        rt.append("                new TimeOfDayPreset { name = \"" + name + "\", hour = " + str(hour) + "f, sunIntensity = " + str(intensity) + "f, sunColor = new Color(" + sun_col + "), sunAngle = " + str(angle) + "f, ambientLight = new Color(" + amb + "), fogDensity = " + str(fog_d) + "f, fogColor = new Color(" + fog_c + ") },")
    rt.append("            };")
    rt.append("        }")
    rt.append("    }")
    rt.append("}")
    runtime_cs = "\n".join(rt)

    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_DayNightSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Create Day Night Cycle\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        GameObject go = new GameObject(\"VB_DayNightCycleManager\");")
    ed.append("        go.AddComponent<" + ns + ".VB_DayNightCycleManager>();")
    ed.append("        if (Object.FindObjectOfType<Light>() == null)")
    ed.append("        {")
    ed.append("            GameObject lightGo = new GameObject(\"VB_DirectionalLight\");")
    ed.append("            Light light = lightGo.AddComponent<Light>();")
    ed.append("            light.type = LightType.Directional;")
    ed.append("            light.shadows = LightShadows.Soft;")
    ed.append("        }")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("        Debug.Log(\"[VeilBreakers] Day/night cycle manager created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# RPG-11: NPC placement
# ---------------------------------------------------------------------------


def generate_npc_placement_script(
    npc_roles: Optional[list[str]] = None,
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str, str]:
    """Generate C# for NPC placement data and manager.

    Returns:
        (so_cs, runtime_cs, editor_cs) triple.
    """
    if npc_roles is None:
        npc_roles = ["shopkeeper", "quest_giver", "bartender", "guard"]
    ns = _safe_namespace(namespace)

    # ----- ScriptableObject: NPCPlacementData -----
    so: list[str] = []
    so.append("using System;")
    so.append("using UnityEngine;")
    so.append("")
    so.append("namespace " + ns)
    so.append("{")
    so.append("    public enum NPCRole")
    so.append("    {")
    for i, role in enumerate(npc_roles):
        safe_role = _sanitize_cs_identifier(role)
        pascal = "".join(w.capitalize() for w in safe_role.split("_"))
        comma = "," if i < len(npc_roles) - 1 else ""
        so.append("        " + pascal + comma)
    so.append("    }")
    so.append("")
    so.append("    [Serializable]")
    so.append("    public class NPCSlot")
    so.append("    {")
    so.append("        public string npcName;")
    so.append("        public NPCRole role;")
    so.append("        public Vector3 position;")
    so.append("        public Quaternion rotation = Quaternion.identity;")
    so.append("        public string prefabPath;")
    so.append("    }")
    so.append("")
    so.append("    [CreateAssetMenu(fileName = \"NewNPCPlacement\", menuName = \"VeilBreakers/NPC Placement\")]")
    so.append("    public class VB_NPCPlacementData : ScriptableObject")
    so.append("    {")
    so.append("        public string locationName;")
    so.append("        public NPCSlot[] slots;")
    so.append("    }")
    so.append("}")
    so_cs = "\n".join(so)

    # ----- Runtime -----
    rt: list[str] = []
    rt.append("using System.Collections.Generic;")
    rt.append("using UnityEngine;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    rt.append("    /// <summary>")
    rt.append("    /// Reads NPC placement SO data and instantiates NPCs at designated positions.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public class VB_NPCPlacementManager : MonoBehaviour")
    rt.append("    {")
    rt.append("        [SerializeField] private VB_NPCPlacementData _placementData;")
    rt.append("        [SerializeField] private GameObject _fallbackPrefab;")
    rt.append("        private List<GameObject> _spawnedNPCs = new List<GameObject>();")
    rt.append("")
    rt.append("        private void Start() { SpawnNPCs(); }")
    rt.append("")
    rt.append("        public void SpawnNPCs()")
    rt.append("        {")
    rt.append("            if (_placementData == null || _placementData.slots == null) return;")
    rt.append("            foreach (NPCSlot slot in _placementData.slots)")
    rt.append("            {")
    rt.append("                GameObject prefab = null;")
    rt.append("                if (!string.IsNullOrEmpty(slot.prefabPath))")
    rt.append("                    prefab = Resources.Load<GameObject>(slot.prefabPath);")
    rt.append("                if (prefab == null) prefab = _fallbackPrefab;")
    rt.append("                if (prefab == null) continue;")
    rt.append("                GameObject npc = Instantiate(prefab, slot.position, slot.rotation);")
    rt.append("                npc.name = !string.IsNullOrEmpty(slot.npcName) ? slot.npcName : slot.role.ToString();")
    rt.append("                _spawnedNPCs.Add(npc);")
    rt.append("            }")
    rt.append("        }")
    rt.append("")
    rt.append("        public void DespawnAll()")
    rt.append("        {")
    rt.append("            foreach (GameObject npc in _spawnedNPCs)")
    rt.append("                if (npc != null) Destroy(npc);")
    rt.append("            _spawnedNPCs.Clear();")
    rt.append("        }")
    rt.append("    }")
    rt.append("}")
    runtime_cs = "\n".join(rt)

    # ----- Editor -----
    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_NPCPlacementSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Setup NPC Placement\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        var data = ScriptableObject.CreateInstance<" + ns + ".VB_NPCPlacementData>();")
    ed.append("        data.locationName = \"NewLocation\";")
    ed.append("        AssetDatabase.CreateAsset(data, \"Assets/Data/NPCPlacement_NewLocation.asset\");")
    ed.append("        GameObject go = new GameObject(\"VB_NPCPlacementManager\");")
    ed.append("        go.AddComponent<" + ns + ".VB_NPCPlacementManager>();")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("        Debug.Log(\"[VeilBreakers] NPC placement manager created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (so_cs, runtime_cs, editor_cs)


# ---------------------------------------------------------------------------
# RPG-12: Dungeon lighting
# ---------------------------------------------------------------------------


def generate_dungeon_lighting_script(
    torch_spacing: float = 5.0,
    torch_light_range: float = 8.0,
    torch_color: Optional[list[float]] = None,
    fog_density: float = 0.03,
    fog_color: Optional[list[float]] = None,
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate C# for dungeon lighting with torch sconces and atmospheric fog.

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    if torch_color is None:
        torch_color = [1.0, 0.7, 0.3, 1.0]
    if fog_color is None:
        fog_color = [0.1, 0.08, 0.06]
    ns = _safe_namespace(namespace)
    tc = ", ".join(str(c) + "f" for c in torch_color[:3])
    fc = ", ".join(str(c) + "f" for c in fog_color[:3])

    rt: list[str] = []
    rt.append("using System.Collections.Generic;")
    rt.append("using UnityEngine;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    rt.append("    /// <summary>")
    rt.append("    /// Sets up dungeon lighting with torch sconces at regular intervals,")
    rt.append("    /// point lights for warm illumination pools, and atmospheric fog.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public class VB_DungeonLightingSetup : MonoBehaviour")
    rt.append("    {")
    rt.append("        [Header(\"Torch Settings\")]")
    rt.append("        [SerializeField] private float _torchSpacing = " + str(torch_spacing) + "f;")
    rt.append("        [SerializeField] private float _torchLightRange = " + str(torch_light_range) + "f;")
    rt.append("        [SerializeField] private Color _torchColor = new Color(" + tc + ");")
    rt.append("        [SerializeField] private float _torchIntensity = 1.5f;")
    rt.append("        [SerializeField] private LightShadows _shadowType = LightShadows.Soft;")
    rt.append("        [Header(\"Torch Prefab\")]")
    rt.append("        [SerializeField] private GameObject _torchSconcePrefab;")
    rt.append("        [Header(\"Fog Settings\")]")
    rt.append("        [SerializeField] private float _fogDensity = " + str(fog_density) + "f;")
    rt.append("        [SerializeField] private Color _fogColor = new Color(" + fc + ");")
    rt.append("        [SerializeField] private bool _enableFog = true;")
    rt.append("        [Header(\"Corridor Path\")]")
    rt.append("        [SerializeField] private Transform[] _pathPoints;")
    rt.append("        private List<GameObject> _placedTorches = new List<GameObject>();")
    rt.append("")
    rt.append("        /// <summary>Places torch sconces every 4-6m along corridor path.</summary>")
    rt.append("        public void SetupLighting()")
    rt.append("        {")
    rt.append("            ClearTorches();")
    rt.append("            SetupFog();")
    rt.append("            if (_pathPoints == null || _pathPoints.Length < 2) return;")
    rt.append("            float accumulated = 0f;")
    rt.append("            for (int i = 0; i < _pathPoints.Length - 1; i++)")
    rt.append("            {")
    rt.append("                Vector3 start = _pathPoints[i].position;")
    rt.append("                Vector3 end = _pathPoints[i + 1].position;")
    rt.append("                float segLength = Vector3.Distance(start, end);")
    rt.append("                Vector3 dir = (end - start).normalized;")
    rt.append("                while (accumulated < segLength)")
    rt.append("                {")
    rt.append("                    Vector3 pos = start + dir * accumulated;")
    rt.append("                    PlaceTorch(pos, dir);")
    rt.append("                    accumulated += _torchSpacing;")
    rt.append("                }")
    rt.append("                accumulated -= segLength;")
    rt.append("            }")
    rt.append("        }")
    rt.append("")
    rt.append("        private void PlaceTorch(Vector3 position, Vector3 corridorDir)")
    rt.append("        {")
    rt.append("            Vector3 wallOffset = Vector3.Cross(corridorDir, Vector3.up).normalized * 1.5f;")
    rt.append("            Vector3 torchPos = position + wallOffset + Vector3.up * 2f;")
    rt.append("            GameObject torchGo;")
    rt.append("            if (_torchSconcePrefab != null)")
    rt.append("                torchGo = Instantiate(_torchSconcePrefab, torchPos, Quaternion.identity, transform);")
    rt.append("            else")
    rt.append("            {")
    rt.append("                torchGo = new GameObject(\"Torch_Sconce\");")
    rt.append("                torchGo.transform.position = torchPos;")
    rt.append("                torchGo.transform.SetParent(transform);")
    rt.append("            }")
    rt.append("            Light pointLight = torchGo.AddComponent<Light>();")
    rt.append("            pointLight.type = LightType.Point;")
    rt.append("            pointLight.range = _torchLightRange;")
    rt.append("            pointLight.color = _torchColor;")
    rt.append("            pointLight.intensity = _torchIntensity;")
    rt.append("            pointLight.shadows = _shadowType;")
    rt.append("            _placedTorches.Add(torchGo);")
    rt.append("        }")
    rt.append("")
    rt.append("        private void SetupFog()")
    rt.append("        {")
    rt.append("            RenderSettings.fog = _enableFog;")
    rt.append("            RenderSettings.fogMode = FogMode.Exponential;")
    rt.append("            RenderSettings.fogDensity = _fogDensity;")
    rt.append("            RenderSettings.fogColor = _fogColor;")
    rt.append("        }")
    rt.append("")
    rt.append("        public void ClearTorches()")
    rt.append("        {")
    rt.append("            foreach (GameObject torch in _placedTorches)")
    rt.append("                if (torch != null) DestroyImmediate(torch);")
    rt.append("            _placedTorches.Clear();")
    rt.append("        }")
    rt.append("    }")
    rt.append("}")
    runtime_cs = "\n".join(rt)

    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_DungeonLightingSetupEditor")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Setup Dungeon Lighting\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        GameObject go = new GameObject(\"VB_DungeonLightingSetup\");")
    ed.append("        go.AddComponent<" + ns + ".VB_DungeonLightingSetup>();")
    ed.append("        for (int i = 0; i < 4; i++)")
    ed.append("        {")
    ed.append("            GameObject point = new GameObject($\"PathPoint_{i}\");")
    ed.append("            point.transform.SetParent(go.transform);")
    ed.append("            point.transform.localPosition = new Vector3(i * 10f, 0f, 0f);")
    ed.append("        }")
    ed.append("        Selection.activeGameObject = go;")
    ed.append("        Debug.Log(\"[VeilBreakers] Dungeon lighting setup created.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# RPG-13: Terrain-building blending
# ---------------------------------------------------------------------------


def generate_terrain_building_blend_script(
    blend_radius: float = 2.0,
    decal_material_path: str = "Materials/TerrainBlendDecal",
    depression_depth: float = 0.1,
    vertex_color_falloff: float = 1.5,
    namespace: str = "VeilBreakers.WorldSystems",
) -> tuple[str, str]:
    """Generate C# for terrain-building blend (vertex color + decal + depression).

    Returns:
        (editor_cs, runtime_cs) tuple.
    """
    ns = _safe_namespace(namespace)

    rt: list[str] = []
    rt.append("using UnityEngine;")
    rt.append("using UnityEngine.Rendering.Universal;")
    rt.append("")
    rt.append("namespace " + ns)
    rt.append("{")
    rt.append("    /// <summary>")
    rt.append("    /// Blends terrain with buildings: vertex color painting at base,")
    rt.append("    /// decal projector for ground transition, terrain height depression.")
    rt.append("    /// Generated by VeilBreakers MCP toolkit.")
    rt.append("    /// </summary>")
    rt.append("    public class VB_TerrainBuildingBlend : MonoBehaviour")
    rt.append("    {")
    rt.append("        [Header(\"Blend Settings\")]")
    rt.append("        [SerializeField] private float _blendRadius = " + str(blend_radius) + "f;")
    rt.append("        [SerializeField] private float _vertexColorFalloff = " + str(vertex_color_falloff) + "f;")
    rt.append("        [SerializeField] private Color _baseBlendColor = new Color(0.3f, 0.25f, 0.15f, 1f);")
    rt.append("        [Header(\"Decal\")]")
    rt.append("        [SerializeField] private Material _decalMaterial;")
    rt.append("        [SerializeField] private float _decalSize = 4f;")
    rt.append("        [Header(\"Terrain Depression\")]")
    rt.append("        [SerializeField] private float _depressionDepth = " + str(depression_depth) + "f;")
    rt.append("        [SerializeField] private Terrain _terrain;")
    rt.append("")
    rt.append("        public void ApplyBlend() { PaintVertexColors(); PlaceDecalProjector(); DepressTerrain(); }")
    rt.append("")
    rt.append("        public void PaintVertexColors()")
    rt.append("        {")
    rt.append("            MeshFilter mf = GetComponentInChildren<MeshFilter>();")
    rt.append("            if (mf == null || mf.sharedMesh == null) return;")
    rt.append("            Mesh mesh = Instantiate(mf.sharedMesh);")
    rt.append("            Vector3[] vertices = mesh.vertices;")
    rt.append("            Color[] colors = new Color[vertices.Length];")
    rt.append("            float minY = float.MaxValue;")
    rt.append("            foreach (Vector3 v in vertices) if (v.y < minY) minY = v.y;")
    rt.append("            for (int i = 0; i < vertices.Length; i++)")
    rt.append("            {")
    rt.append("                float height = vertices[i].y - minY;")
    rt.append("                float t = Mathf.Clamp01(1f - (height / (_blendRadius * _vertexColorFalloff)));")
    rt.append("                colors[i] = Color.Lerp(Color.white, _baseBlendColor, t);")
    rt.append("            }")
    rt.append("            mesh.colors = colors;")
    rt.append("            mf.mesh = mesh;")
    rt.append("        }")
    rt.append("")
    rt.append("        public void PlaceDecalProjector()")
    rt.append("        {")
    rt.append("            GameObject decalGo = new GameObject(\"VB_BlendDecal\");")
    rt.append("            decalGo.transform.SetParent(transform);")
    rt.append("            decalGo.transform.localPosition = Vector3.down * 0.1f;")
    rt.append("            decalGo.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);")
    rt.append("            DecalProjector decal = decalGo.AddComponent<DecalProjector>();")
    rt.append("            decal.material = _decalMaterial;")
    rt.append("            decal.size = new Vector3(_decalSize, _decalSize, 1f);")
    rt.append("            decal.fadeFactor = 1f;")
    rt.append("        }")
    rt.append("")
    rt.append("        public void DepressTerrain()")
    rt.append("        {")
    rt.append("            if (_terrain == null) return;")
    rt.append("            TerrainData terrainData = _terrain.terrainData;")
    rt.append("            Vector3 terrainPos = _terrain.transform.position;")
    rt.append("            Vector3 buildingPos = transform.position;")
    rt.append("            int mapW = terrainData.heightmapResolution;")
    rt.append("            int mapH = terrainData.heightmapResolution;")
    rt.append("            float relX = (buildingPos.x - terrainPos.x) / terrainData.size.x;")
    rt.append("            float relZ = (buildingPos.z - terrainPos.z) / terrainData.size.z;")
    rt.append("            int centerX = Mathf.RoundToInt(relX * mapW);")
    rt.append("            int centerZ = Mathf.RoundToInt(relZ * mapH);")
    rt.append("            int radiusSamples = Mathf.RoundToInt((_blendRadius / terrainData.size.x) * mapW);")
    rt.append("            int startX = Mathf.Max(0, centerX - radiusSamples);")
    rt.append("            int startZ = Mathf.Max(0, centerZ - radiusSamples);")
    rt.append("            int width = Mathf.Min(radiusSamples * 2, mapW - startX);")
    rt.append("            int height = Mathf.Min(radiusSamples * 2, mapH - startZ);")
    rt.append("            float[,] heights = terrainData.GetHeights(startX, startZ, width, height);")
    rt.append("            float depthNorm = _depressionDepth / terrainData.size.y;")
    rt.append("            for (int z = 0; z < height; z++)")
    rt.append("                for (int x = 0; x < width; x++)")
    rt.append("                {")
    rt.append("                    float dx = (startX + x - centerX) / (float)radiusSamples;")
    rt.append("                    float dz = (startZ + z - centerZ) / (float)radiusSamples;")
    rt.append("                    float dist = Mathf.Sqrt(dx * dx + dz * dz);")
    rt.append("                    if (dist <= 1f) heights[z, x] -= depthNorm * (1f - dist);")
    rt.append("                }")
    rt.append("            terrainData.SetHeights(startX, startZ, heights);")
    rt.append("        }")
    rt.append("    }")
    rt.append("}")
    runtime_cs = "\n".join(rt)

    ed: list[str] = []
    ed.append("using UnityEngine;")
    ed.append("using UnityEditor;")
    ed.append("")
    ed.append("public static class VeilBreakers_TerrainBlendSetup")
    ed.append("{")
    ed.append("    [MenuItem(\"VeilBreakers/World/Blend Terrain Building\")]")
    ed.append("    public static void Execute()")
    ed.append("    {")
    ed.append("        if (Selection.activeGameObject == null)")
    ed.append("        {")
    ed.append("            Debug.LogWarning(\"[VeilBreakers] Select a building GameObject first.\");")
    ed.append("            return;")
    ed.append("        }")
    ed.append("        Selection.activeGameObject.AddComponent<" + ns + ".VB_TerrainBuildingBlend>();")
    ed.append("        Debug.Log(\"[VeilBreakers] Terrain-building blend component added.\");")
    ed.append("    }")
    ed.append("}")
    editor_cs = "\n".join(ed)

    return (editor_cs, runtime_cs)


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
    "generate_fast_travel_script",
    "generate_puzzle_mechanics_script",
    "generate_trap_system_script",
    "generate_spatial_loot_script",
    "generate_weather_system_script",
    "generate_day_night_cycle_script",
    "generate_npc_placement_script",
    "generate_dungeon_lighting_script",
    "generate_terrain_building_blend_script",
]
