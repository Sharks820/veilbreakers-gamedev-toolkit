"""UX C# template generators for Unity gameplay HUD elements.

Each function returns a complete C# source string (or tuple of strings for
multi-file generators) for common action RPG UX elements: minimap with
orthographic camera render texture, floating damage numbers with PrimeTween
and object pooling, context-sensitive interaction prompts with Input System
rebind display, PrimeTween UI animation sequences, and TextMeshPro font
asset creation and component setup.

All generators use PrimeTween exclusively -- NEVER DOTween.

Exports:
    generate_minimap_script              -- UIX-01: Minimap with orthographic camera + RenderTexture
    generate_damage_numbers_script       -- UIX-03: Floating damage numbers with PrimeTween + ObjectPool
    generate_interaction_prompts_script  -- UIX-04: Context-sensitive prompts with Input System rebind
    generate_primetween_sequence_script  -- SHDR-04: PrimeTween UI animation sequences
    generate_tmp_font_asset_script       -- PIPE-10: TMP font asset creation editor script
    generate_tmp_component_script        -- PIPE-10: TMP component setup editor script
"""

from __future__ import annotations

import re
from typing import Optional

from ._cs_sanitize import sanitize_cs_string, sanitize_cs_identifier


# ---------------------------------------------------------------------------
# Namespace helper
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
    """Sanitize a C# namespace string."""
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


def _wrap_namespace(lines: list[str], namespace: str) -> list[str]:
    """Wrap lines in a namespace block if namespace is non-empty."""
    if not namespace:
        return lines
    ns = _safe_namespace(namespace)
    wrapped = [f"namespace {ns}", "{"]
    for line in lines:
        if line.strip():
            wrapped.append(f"    {line}")
        else:
            wrapped.append("")
    wrapped.append("}")
    return wrapped


# ---------------------------------------------------------------------------
# Brand color definitions (VeilBreakers 10 brands)
# ---------------------------------------------------------------------------

_BRAND_COLORS = {
    "IRON": ("0.6f", "0.6f", "0.6f", "1f"),
    "SAVAGE": ("0.9f", "0.2f", "0.1f", "1f"),
    "SURGE": ("0.2f", "0.4f", "1f", "1f"),
    "VENOM": ("0.2f", "0.8f", "0.2f", "1f"),
    "DREAD": ("0.6f", "0.1f", "0.9f", "1f"),
    "LEECH": ("0.4f", "0.15f", "0.5f", "1f"),
    "GRACE": ("1f", "0.85f", "0.4f", "1f"),
    "MEND": ("0.13f", "0.7f", "0.55f", "1f"),
    "RUIN": ("0.5f", "0.35f", "0.2f", "1f"),
    "VOID": ("0.15f", "0f", "0.3f", "1f"),
}


# ---------------------------------------------------------------------------
# UIX-01: Minimap with orthographic camera + RenderTexture
# ---------------------------------------------------------------------------


def generate_minimap_script(
    name: str = "Minimap",
    render_texture_size: int = 256,
    zoom: float = 50.0,
    follow_target: str = "Player",
    culling_layers: Optional[list[str]] = None,
    compass_enabled: bool = True,
    marker_types: Optional[list[str]] = None,
    update_interval: int = 3,
    namespace: str = "",
) -> tuple[str, str]:
    """Generate minimap editor setup script and runtime MonoBehaviour.

    Returns a tuple of (editor_cs, runtime_cs). The editor script creates
    the orthographic Camera, RenderTexture, and Canvas/RawImage setup. The
    runtime script follows the player transform with 1:1 positional accuracy,
    manages world-space markers, and optionally renders a compass ring.

    Args:
        name: Base name for the minimap system.
        render_texture_size: Size of the render texture (square).
        zoom: Orthographic size for the minimap camera.
        follow_target: Tag of the target to follow.
        culling_layers: Layer names for the minimap camera culling mask.
        compass_enabled: Whether to include compass rotation.
        marker_types: List of marker type names for POI tracking.
        update_interval: Frame interval for camera position updates.
        namespace: Optional C# namespace.

    Returns:
        Tuple of (editor_cs: str, runtime_cs: str).
    """
    safe_name = sanitize_cs_identifier(name)
    safe_target = sanitize_cs_string(follow_target)
    layers = culling_layers or ["Minimap", "Terrain"]
    markers = marker_types or ["Quest", "NPC", "Enemy", "POI"]

    # -----------------------------------------------------------------------
    # Editor script
    # -----------------------------------------------------------------------
    editor_lines: list[str] = []
    editor_lines.append("using UnityEngine;")
    editor_lines.append("using UnityEditor;")
    editor_lines.append("using UnityEngine.UI;")
    editor_lines.append("")

    e_body: list[str] = []
    e_body.append(f"public class {safe_name}Setup : EditorWindow")
    e_body.append("{")
    e_body.append(f'    [MenuItem("VeilBreakers/UX/Setup {safe_name}")]')
    e_body.append(f"    public static void Setup{safe_name}()")
    e_body.append("    {")
    e_body.append(f'        // Create RenderTexture asset ({render_texture_size}x{render_texture_size})')
    e_body.append(f'        if (!AssetDatabase.IsValidFolder("Assets/Textures"))')
    e_body.append(f'            AssetDatabase.CreateFolder("Assets", "Textures");')
    e_body.append(f'        if (!AssetDatabase.IsValidFolder("Assets/Textures/UI"))')
    e_body.append(f'            AssetDatabase.CreateFolder("Assets/Textures", "UI");')
    e_body.append(f"        var rt = new RenderTexture({render_texture_size}, {render_texture_size}, 16, RenderTextureFormat.ARGB32);")
    e_body.append(f'        rt.name = "{safe_name}_RT";')
    e_body.append(f'        AssetDatabase.CreateAsset(rt, "Assets/Textures/UI/{safe_name}_RT.asset");')
    e_body.append("")
    e_body.append("        // Create minimap camera")
    e_body.append(f'        var camObj = new GameObject("{safe_name}Camera");')
    e_body.append("        var cam = camObj.AddComponent<Camera>();")
    e_body.append("        cam.orthographic = true;")
    e_body.append(f"        cam.orthographicSize = {zoom}f;")
    e_body.append("        cam.clearFlags = CameraClearFlags.SolidColor;")
    e_body.append("        cam.backgroundColor = new Color(0.05f, 0.05f, 0.1f, 1f);")
    e_body.append("        cam.targetTexture = rt;")
    e_body.append("        cam.transform.rotation = Quaternion.Euler(90, 0, 0);")
    e_body.append("        cam.transform.position = new Vector3(0, 100f, 0);")
    # Set culling mask
    layer_str = " | ".join([f'LayerMask.GetMask("{sanitize_cs_string(layer)}")' for layer in layers])
    e_body.append(f"        cam.cullingMask = {layer_str};")
    e_body.append("")
    e_body.append("        // Create Canvas with RawImage for minimap display")
    e_body.append(f'        var canvasObj = new GameObject("{safe_name}Canvas");')
    e_body.append("        var canvas = canvasObj.AddComponent<Canvas>();")
    e_body.append("        canvas.renderMode = RenderMode.ScreenSpaceOverlay;")
    e_body.append("        canvas.sortingOrder = 100;")
    e_body.append("        canvasObj.AddComponent<CanvasScaler>();")
    e_body.append("        canvasObj.AddComponent<GraphicRaycaster>();")
    e_body.append("")
    e_body.append(f'        var rawImgObj = new GameObject("{safe_name}Display");')
    e_body.append("        rawImgObj.transform.SetParent(canvasObj.transform, false);")
    e_body.append("        var rawImg = rawImgObj.AddComponent<RawImage>();")
    e_body.append("        rawImg.texture = rt;")
    e_body.append("        var rect = rawImgObj.GetComponent<RectTransform>();")
    e_body.append(f"        rect.sizeDelta = new Vector2({render_texture_size}, {render_texture_size});")
    e_body.append("        rect.anchorMin = new Vector2(1, 1);")
    e_body.append("        rect.anchorMax = new Vector2(1, 1);")
    e_body.append("        rect.pivot = new Vector2(1, 1);")
    e_body.append(f"        rect.anchoredPosition = new Vector2(-10, -10);")
    e_body.append("")
    e_body.append(f'        // Add runtime component')
    e_body.append(f"        camObj.AddComponent<{safe_name}Controller>();")
    e_body.append("")
    e_body.append("        AssetDatabase.SaveAssets();")
    e_body.append(f'        Debug.Log("{safe_name} setup complete.");')
    e_body.append("    }")
    e_body.append("}")

    if namespace:
        editor_lines.extend(_wrap_namespace(e_body, namespace))
    else:
        editor_lines.extend(e_body)

    editor_cs = "\n".join(editor_lines)

    # -----------------------------------------------------------------------
    # Runtime script
    # -----------------------------------------------------------------------
    runtime_lines: list[str] = []
    runtime_lines.append("using UnityEngine;")
    runtime_lines.append("using UnityEngine.UI;")
    runtime_lines.append("using System.Collections.Generic;")
    runtime_lines.append("")

    r_body: list[str] = []
    r_body.append(f"public class {safe_name}Controller : MonoBehaviour")
    r_body.append("{")
    r_body.append(f"    [Header(\"Target\")]")
    r_body.append(f'    [SerializeField] private string _targetTag = "{safe_target}";')
    r_body.append(f"    [SerializeField] private float _cameraHeight = 100f;")
    r_body.append("")
    r_body.append(f"    [Header(\"Camera Settings\")]")
    r_body.append(f"    [SerializeField] private float _orthographicSize = {zoom}f;")
    r_body.append(f"    [SerializeField] private int _updateInterval = {update_interval};")
    r_body.append("")
    if compass_enabled:
        r_body.append(f"    [Header(\"Compass\")]")
        r_body.append(f"    [SerializeField] private RectTransform _compassRing;")
        r_body.append("")
    r_body.append(f"    [Header(\"Markers\")]")
    r_body.append(f"    [SerializeField] private RectTransform _markerContainer;")
    r_body.append(f"    [SerializeField] private GameObject _markerPrefab;")
    r_body.append("")
    r_body.append("    private Camera _minimapCamera;")
    r_body.append("    private Transform _target;")
    r_body.append("    private int _frameCount;")
    r_body.append("")
    r_body.append("    // World-space marker tracking")
    r_body.append("    private Dictionary<string, Transform> _trackedMarkers = new Dictionary<string, Transform>();")
    r_body.append("    private Dictionary<string, RectTransform> _markerIcons = new Dictionary<string, RectTransform>();")
    r_body.append("")
    # Marker type enum
    r_body.append("    public enum MarkerType")
    r_body.append("    {")
    for m in markers:
        r_body.append(f"        {sanitize_cs_identifier(m)},")
    r_body.append("    }")
    r_body.append("")
    # Zoom property
    r_body.append("    public float Zoom")
    r_body.append("    {")
    r_body.append("        get => _orthographicSize;")
    r_body.append("        set")
    r_body.append("        {")
    r_body.append("            _orthographicSize = value;")
    r_body.append("            if (_minimapCamera != null)")
    r_body.append("                _minimapCamera.orthographicSize = _orthographicSize;")
    r_body.append("        }")
    r_body.append("    }")
    r_body.append("")
    # Awake
    r_body.append("    private void Awake()")
    r_body.append("    {")
    r_body.append("        _minimapCamera = GetComponent<Camera>();")
    r_body.append("        if (_minimapCamera != null)")
    r_body.append("        {")
    r_body.append("            _minimapCamera.orthographic = true;")
    r_body.append("            _minimapCamera.orthographicSize = _orthographicSize;")
    r_body.append("            _minimapCamera.clearFlags = CameraClearFlags.SolidColor;")
    r_body.append("            _minimapCamera.backgroundColor = new Color(0.05f, 0.05f, 0.1f, 1f);")
    r_body.append("            _minimapCamera.transform.rotation = Quaternion.Euler(90, 0, 0);")
    # Set culling mask at runtime too
    layer_mask_str = " | ".join([f'LayerMask.GetMask("{sanitize_cs_string(layer)}")' for layer in layers])
    r_body.append(f"            _minimapCamera.cullingMask = {layer_mask_str};")
    r_body.append("        }")
    r_body.append("    }")
    r_body.append("")
    # LateUpdate -- follows player with 1:1 positional accuracy
    r_body.append("    private void LateUpdate()")
    r_body.append("    {")
    r_body.append("        _frameCount++;")
    r_body.append(f"        if (_frameCount % _updateInterval != 0) return;")
    r_body.append("")
    r_body.append("        if (_target == null)")
    r_body.append("        {")
    r_body.append("            var targetObj = GameObject.FindWithTag(_targetTag);")
    r_body.append("            if (targetObj != null) _target = targetObj.transform;")
    r_body.append("            else return;")
    r_body.append("        }")
    r_body.append("")
    r_body.append("        // Follow player position with 1:1 positional accuracy")
    r_body.append("        var target = _target.position;")
    r_body.append("        _minimapCamera.transform.position = new Vector3(target.x, _minimapCamera.transform.position.y, target.z);")
    r_body.append("")
    if compass_enabled:
        r_body.append("        // Compass rotation matches player facing direction")
        r_body.append("        if (_compassRing != null)")
        r_body.append("        {")
        r_body.append("            float angle = _target.eulerAngles.y;")
        r_body.append("            _compassRing.localRotation = Quaternion.Euler(0, 0, angle);")
        r_body.append("        }")
        r_body.append("")
    r_body.append("        // Update marker positions via world-to-viewport conversion")
    r_body.append("        UpdateMarkerPositions();")
    r_body.append("    }")
    r_body.append("")
    # AddMarker
    r_body.append("    public void AddMarker(string id, Transform worldTransform)")
    r_body.append("    {")
    r_body.append("        if (_trackedMarkers.ContainsKey(id)) return;")
    r_body.append("        _trackedMarkers[id] = worldTransform;")
    r_body.append("")
    r_body.append("        if (_markerPrefab != null && _markerContainer != null)")
    r_body.append("        {")
    r_body.append("            var icon = Instantiate(_markerPrefab, _markerContainer).GetComponent<RectTransform>();")
    r_body.append("            _markerIcons[id] = icon;")
    r_body.append("        }")
    r_body.append("    }")
    r_body.append("")
    # RemoveMarker
    r_body.append("    public void RemoveMarker(string id)")
    r_body.append("    {")
    r_body.append("        _trackedMarkers.Remove(id);")
    r_body.append("        if (_markerIcons.TryGetValue(id, out var icon))")
    r_body.append("        {")
    r_body.append("            Destroy(icon.gameObject);")
    r_body.append("            _markerIcons.Remove(id);")
    r_body.append("        }")
    r_body.append("    }")
    r_body.append("")
    # UpdateMarkerPositions
    r_body.append("    private void UpdateMarkerPositions()")
    r_body.append("    {")
    r_body.append("        foreach (var kvp in _trackedMarkers)")
    r_body.append("        {")
    r_body.append("            if (kvp.Value == null || !_markerIcons.ContainsKey(kvp.Key)) continue;")
    r_body.append("            var viewportPos = _minimapCamera.WorldToViewportPoint(kvp.Value.position);")
    r_body.append("            var icon = _markerIcons[kvp.Key];")
    r_body.append("            if (_markerContainer != null)")
    r_body.append("            {")
    r_body.append("                var containerSize = _markerContainer.rect.size;")
    r_body.append("                icon.anchoredPosition = new Vector2(")
    r_body.append("                    (viewportPos.x - 0.5f) * containerSize.x,")
    r_body.append("                    (viewportPos.y - 0.5f) * containerSize.y")
    r_body.append("                );")
    r_body.append("            }")
    r_body.append("            icon.gameObject.SetActive(viewportPos.x >= 0 && viewportPos.x <= 1 && viewportPos.y >= 0 && viewportPos.y <= 1);")
    r_body.append("        }")
    r_body.append("    }")
    r_body.append("}")

    if namespace:
        runtime_lines.extend(_wrap_namespace(r_body, namespace))
    else:
        runtime_lines.extend(r_body)

    runtime_cs = "\n".join(runtime_lines)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# UIX-03: Floating damage numbers with PrimeTween + ObjectPool
# ---------------------------------------------------------------------------


def generate_damage_numbers_script(
    name: str = "DamageNumbers",
    pool_size: int = 20,
    float_height: float = 80.0,
    duration: float = 0.8,
    crit_scale: float = 1.5,
    namespace: str = "",
) -> str:
    """Generate floating damage numbers MonoBehaviour with PrimeTween + ObjectPool.

    Uses ObjectPool<GameObject> from UnityEngine.Pool for zero-allocation spawning
    and PrimeTween for float-up + fade animations. Color-coded by VeilBreakers
    10 brand damage types.

    Args:
        name: Class name for the damage number system.
        pool_size: Pre-allocated pool size for damage number instances.
        float_height: Pixel height the number floats upward.
        duration: Duration of the float + fade animation.
        crit_scale: Scale multiplier for critical hit text.
        namespace: Optional C# namespace.

    Returns:
        C# MonoBehaviour source string.
    """
    safe_name = sanitize_cs_identifier(name)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.Pool;")
    lines.append("using UnityEngine.UI;")
    lines.append("using TMPro;")
    lines.append("using PrimeTween;")
    lines.append("using System.Collections.Generic;")
    lines.append("")

    body: list[str] = []
    body.append(f"public class {safe_name}Manager : MonoBehaviour")
    body.append("{")
    body.append(f"    [Header(\"Pool Settings\")]")
    body.append(f"    [SerializeField] private GameObject _damageNumberPrefab;")
    body.append(f"    [SerializeField] private int _poolSize = {pool_size};")
    body.append("")
    body.append(f"    [Header(\"Animation\")]")
    body.append(f"    [SerializeField] private float _floatHeight = {float_height}f;")
    body.append(f"    [SerializeField] private float _duration = {duration}f;")
    body.append(f"    [SerializeField] private float _critScale = {crit_scale}f;")
    body.append(f"    [SerializeField] private float _randomXRange = 20f;")
    body.append("")
    body.append("    private ObjectPool<GameObject> _pool;")
    body.append("    private Camera _mainCamera;")
    body.append("")
    body.append("    // VeilBreakers 10 brand damage type colors")
    body.append("    private static readonly Dictionary<string, Color> _damageColors = new Dictionary<string, Color>")
    body.append("    {")
    for brand, (r, g, b, a) in _BRAND_COLORS.items():
        body.append(f'        {{ "{brand}", new Color({r}, {g}, {b}, {a}) }},')
    body.append('        { "Physical", new Color(1f, 1f, 1f, 1f) },')
    body.append("    };")
    body.append("")
    # Awake
    body.append("    private void Awake()")
    body.append("    {")
    body.append("        _mainCamera = Camera.main;")
    body.append("        _pool = new ObjectPool<GameObject>(")
    body.append("            createFunc: CreateDamageNumber,")
    body.append("            actionOnGet: OnGetFromPool,")
    body.append("            actionOnRelease: OnReturnToPool,")
    body.append("            actionOnDestroy: obj => Destroy(obj),")
    body.append(f"            defaultCapacity: _poolSize,")
    body.append(f"            maxSize: _poolSize * 2")
    body.append("        );")
    body.append("")
    body.append("        // Pre-warm the pool")
    body.append("        var preWarm = new List<GameObject>();")
    body.append("        for (int i = 0; i < _poolSize; i++)")
    body.append("            preWarm.Add(_pool.Get());")
    body.append("        foreach (var obj in preWarm)")
    body.append("            _pool.Release(obj);")
    body.append("    }")
    body.append("")
    # Pool callbacks
    body.append("    private GameObject CreateDamageNumber()")
    body.append("    {")
    body.append("        if (_damageNumberPrefab != null)")
    body.append("            return Instantiate(_damageNumberPrefab, transform);")
    body.append("")
    body.append('        var obj = new GameObject("DamageNumber");')
    body.append("        obj.transform.SetParent(transform);")
    body.append("        var rectTransform = obj.AddComponent<RectTransform>();")
    body.append("        var canvasGroup = obj.AddComponent<CanvasGroup>();")
    body.append("        var tmp = obj.AddComponent<TextMeshProUGUI>();")
    body.append("        tmp.alignment = TextAlignmentOptions.Center;")
    body.append("        tmp.fontSize = 36;")
    body.append("        tmp.fontStyle = FontStyles.Bold;")
    body.append("        return obj;")
    body.append("    }")
    body.append("")
    body.append("    private void OnGetFromPool(GameObject obj)")
    body.append("    {")
    body.append("        obj.SetActive(true);")
    body.append("        var cg = obj.GetComponent<CanvasGroup>();")
    body.append("        if (cg != null) cg.alpha = 1f;")
    body.append("        obj.transform.localScale = Vector3.one;")
    body.append("    }")
    body.append("")
    body.append("    private void OnReturnToPool(GameObject obj)")
    body.append("    {")
    body.append("        obj.SetActive(false);")
    body.append("    }")
    body.append("")
    # ShowDamage
    body.append("    /// <summary>")
    body.append("    /// Display a floating damage number at the specified world position.")
    body.append("    /// </summary>")
    body.append("    public void ShowDamage(Vector3 worldPos, float amount, string damageType, bool isCrit)")
    body.append("    {")
    body.append("        var obj = _pool.Get();")
    body.append("        var rect = obj.GetComponent<RectTransform>();")
    body.append("        var canvasGroup = obj.GetComponent<CanvasGroup>();")
    body.append("        var tmp = obj.GetComponent<TextMeshProUGUI>();")
    body.append("")
    body.append("        // Position at world point projected to screen")
    body.append("        if (_mainCamera != null)")
    body.append("        {")
    body.append("            Vector3 screenPos = _mainCamera.WorldToScreenPoint(worldPos);")
    body.append("            rect.position = screenPos;")
    body.append("        }")
    body.append("")
    body.append("        // Random X offset to prevent stacking")
    body.append("        float randomX = Random.Range(-_randomXRange, _randomXRange);")
    body.append("        rect.anchoredPosition += new Vector2(randomX, 0);")
    body.append("        Vector2 start = rect.anchoredPosition;")
    body.append("")
    body.append("        // Format text")
    body.append('        string text = Mathf.RoundToInt(amount).ToString();')
    body.append('        if (isCrit) text += "!";')
    body.append("        tmp.text = text;")
    body.append("")
    body.append("        // Color by damage type")
    body.append("        if (_damageColors.TryGetValue(damageType, out var color))")
    body.append("            tmp.color = color;")
    body.append("        else")
    body.append("            tmp.color = Color.white;")
    body.append("")
    body.append("        // Crit scale")
    body.append("        if (isCrit)")
    body.append("            obj.transform.localScale = Vector3.one * _critScale;")
    body.append("        else")
    body.append("            obj.transform.localScale = Vector3.one;")
    body.append("")
    body.append("        // PrimeTween float-up + fade animation")
    body.append("        canvasGroup.alpha = 1f;")
    body.append("        Sequence.Create()")
    body.append("            .Group(Tween.UIAnchoredPosition(rect, endValue: start + Vector2.up * _floatHeight, duration: _duration, ease: Ease.OutCubic))")
    body.append("            .Group(Tween.Alpha(canvasGroup, endValue: 0f, duration: _duration, ease: Ease.InQuad))")
    body.append("            .OnComplete(() => ReturnToPool(obj));")
    body.append("    }")
    body.append("")
    body.append("    private void ReturnToPool(GameObject obj)")
    body.append("    {")
    body.append("        _pool.Release(obj);")
    body.append("    }")
    body.append("}")

    if namespace:
        lines.extend(_wrap_namespace(body, namespace))
    else:
        lines.extend(body)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# UIX-04: Context-sensitive interaction prompts with Input System rebind
# ---------------------------------------------------------------------------


def generate_interaction_prompts_script(
    name: str = "InteractionPrompt",
    prompt_text: str = "Interact",
    trigger_radius: float = 2.5,
    fade_duration: float = 0.3,
    namespace: str = "",
) -> str:
    """Generate interaction prompt MonoBehaviour with Input System rebind display.

    Creates a proximity-triggered UI prompt that displays the current
    input binding using InputAction.GetBindingDisplayString() for dynamic
    rebind support. Uses PrimeTween for fade animations.

    Args:
        name: Class name for the interaction prompt.
        prompt_text: Default action text shown in prompt.
        trigger_radius: Sphere trigger radius for activation.
        fade_duration: Duration of the fade in/out animation.
        namespace: Optional C# namespace.

    Returns:
        C# MonoBehaviour source string.
    """
    safe_name = sanitize_cs_identifier(name)
    safe_prompt = sanitize_cs_string(prompt_text)

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.InputSystem;")
    lines.append("using UnityEngine.UI;")
    lines.append("using TMPro;")
    lines.append("using PrimeTween;")
    lines.append("")

    body: list[str] = []
    body.append(f"[RequireComponent(typeof(SphereCollider))]")
    body.append(f"public class {safe_name} : MonoBehaviour")
    body.append("{")
    body.append(f"    [Header(\"Interaction\")]")
    body.append(f'    [SerializeField] private string _actionText = "{safe_prompt}";')
    body.append(f"    [SerializeField] private InputActionReference _interactAction;")
    body.append(f"    [SerializeField] private float _triggerRadius = {trigger_radius}f;")
    body.append("")
    body.append(f"    [Header(\"UI\")]")
    body.append(f"    [SerializeField] private Canvas _promptCanvas;")
    body.append(f"    [SerializeField] private TextMeshProUGUI _promptText;")
    body.append(f"    [SerializeField] private CanvasGroup _canvasGroup;")
    body.append(f"    [SerializeField] private float _fadeDuration = {fade_duration}f;")
    body.append("")
    body.append("    private SphereCollider _trigger;")
    body.append("    private Camera _mainCamera;")
    body.append("    private bool _isVisible;")
    body.append("")
    body.append("    private void Awake()")
    body.append("    {")
    body.append("        _mainCamera = Camera.main;")
    body.append("")
    body.append("        // Setup sphere trigger")
    body.append("        _trigger = GetComponent<SphereCollider>();")
    body.append("        _trigger.isTrigger = true;")
    body.append("        _trigger.radius = _triggerRadius;")
    body.append("")
    body.append("        // Create prompt UI if not assigned")
    body.append("        if (_promptCanvas == null)")
    body.append("        {")
    body.append('            var canvasObj = new GameObject("PromptCanvas");')
    body.append("            canvasObj.transform.SetParent(transform);")
    body.append("            canvasObj.transform.localPosition = Vector3.up * 2f;")
    body.append("            _promptCanvas = canvasObj.AddComponent<Canvas>();")
    body.append("            _promptCanvas.renderMode = RenderMode.WorldSpace;")
    body.append("            _canvasGroup = canvasObj.AddComponent<CanvasGroup>();")
    body.append("            _canvasGroup.alpha = 0f;")
    body.append("")
    body.append('            var textObj = new GameObject("PromptText");')
    body.append("            textObj.transform.SetParent(canvasObj.transform, false);")
    body.append("            _promptText = textObj.AddComponent<TextMeshProUGUI>();")
    body.append("            _promptText.alignment = TextAlignmentOptions.Center;")
    body.append("            _promptText.fontSize = 3;")
    body.append("            var textRect = textObj.GetComponent<RectTransform>();")
    body.append("            textRect.sizeDelta = new Vector2(4f, 1f);")
    body.append("        }")
    body.append("")
    body.append("        if (_canvasGroup == null)")
    body.append("            _canvasGroup = _promptCanvas.GetComponent<CanvasGroup>();")
    body.append("        if (_canvasGroup == null)")
    body.append("            _canvasGroup = _promptCanvas.gameObject.AddComponent<CanvasGroup>();")
    body.append("        _canvasGroup.alpha = 0f;")
    body.append("    }")
    body.append("")
    body.append("    private void LateUpdate()")
    body.append("    {")
    body.append("        // Billboard effect: prompt always faces camera")
    body.append("        if (_promptCanvas != null && _mainCamera != null)")
    body.append("        {")
    body.append("            _promptCanvas.transform.LookAt(")
    body.append("                _promptCanvas.transform.position + _mainCamera.transform.forward);")
    body.append("        }")
    body.append("    }")
    body.append("")
    body.append("    private void OnTriggerEnter(Collider other)")
    body.append("    {")
    body.append('        if (!other.CompareTag("Player")) return;')
    body.append("        ShowPrompt();")
    body.append("    }")
    body.append("")
    body.append("    private void OnTriggerExit(Collider other)")
    body.append("    {")
    body.append('        if (!other.CompareTag("Player")) return;')
    body.append("        HidePrompt();")
    body.append("    }")
    body.append("")
    body.append("    private void ShowPrompt()")
    body.append("    {")
    body.append("        _isVisible = true;")
    body.append("        UpdatePromptText();")
    body.append("        Tween.Alpha(_canvasGroup, endValue: 1f, duration: _fadeDuration);")
    body.append("    }")
    body.append("")
    body.append("    private void HidePrompt()")
    body.append("    {")
    body.append("        _isVisible = false;")
    body.append("        Tween.Alpha(_canvasGroup, endValue: 0f, duration: _fadeDuration);")
    body.append("    }")
    body.append("")
    body.append("    private void UpdatePromptText()")
    body.append("    {")
    body.append("        if (_promptText == null) return;")
    body.append("")
    body.append("        // Dynamic key display using Input System rebind")
    body.append('        string keyDisplay = "E";')
    body.append("        if (_interactAction != null && _interactAction.action != null)")
    body.append("        {")
    body.append("            keyDisplay = _interactAction.action.GetBindingDisplayString();")
    body.append("        }")
    body.append("")
    body.append('        _promptText.text = $"[{keyDisplay}] {_actionText}";')
    body.append("    }")
    body.append("")
    body.append("    /// <summary>")
    body.append("    /// Refresh prompt text after input rebinding.")
    body.append("    /// </summary>")
    body.append("    public void OnRebindComplete()")
    body.append("    {")
    body.append("        if (_isVisible) UpdatePromptText();")
    body.append("    }")
    body.append("}")

    if namespace:
        lines.extend(_wrap_namespace(body, namespace))
    else:
        lines.extend(body)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SHDR-04: PrimeTween UI animation sequence generator
# ---------------------------------------------------------------------------

_SEQUENCE_PRESETS = {
    "panel_entrance": "PanelEntrance",
    "panel_exit": "PanelExit",
    "button_hover": "ButtonHover",
    "notification_popup": "NotificationPopup",
    "screen_shake": "ScreenShake",
    "damage_flash": "DamageFlash",
    "item_pickup": "ItemPickup",
    "level_up": "LevelUp",
}


def generate_primetween_sequence_script(
    sequence_type: str = "panel_entrance",
    name: str = "default",
    namespace: str = "",
) -> str:
    """Generate PrimeTween UI animation utility class with static methods.

    Produces a C# utility class with static methods for common UI animation
    patterns using PrimeTween API exclusively (NEVER DOTween).

    Args:
        sequence_type: Preset type selecting the animation pattern.
        name: Custom name for the generated class.
        namespace: Optional C# namespace.

    Returns:
        C# utility class source string.
    """
    safe_name = sanitize_cs_identifier(name)
    class_name = f"VB_{safe_name}Animations" if name != "default" else "VB_UIAnimations"

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEngine.UI;")
    lines.append("using PrimeTween;")
    lines.append("")

    body: list[str] = []
    body.append(f"/// <summary>")
    body.append(f"/// PrimeTween-based UI animation utility. All methods use PrimeTween API exclusively.")
    body.append(f"/// </summary>")
    body.append(f"public static class {class_name}")
    body.append("{")

    # Panel Entrance
    body.append("    /// <summary>Scale + fade panel entrance animation.</summary>")
    body.append("    public static Sequence PanelEntrance(RectTransform panel, CanvasGroup canvasGroup, float duration = 0.4f)")
    body.append("    {")
    body.append("        panel.localScale = Vector3.one * 0.8f;")
    body.append("        canvasGroup.alpha = 0f;")
    body.append("        return Sequence.Create()")
    body.append("            .Group(Tween.Scale(panel, endValue: Vector3.one, duration: duration, ease: Ease.OutBack))")
    body.append("            .Group(Tween.Alpha(canvasGroup, endValue: 1f, duration: duration * 0.5f, ease: Ease.OutCubic));")
    body.append("    }")
    body.append("")

    # Panel Exit
    body.append("    /// <summary>Scale + fade panel exit animation.</summary>")
    body.append("    public static Sequence PanelExit(RectTransform panel, CanvasGroup canvasGroup, float duration = 0.3f)")
    body.append("    {")
    body.append("        return Sequence.Create()")
    body.append("            .Group(Tween.Scale(panel, endValue: Vector3.one * 0.8f, duration: duration, ease: Ease.InQuad))")
    body.append("            .Group(Tween.Alpha(canvasGroup, endValue: 0f, duration: duration, ease: Ease.InQuad));")
    body.append("    }")
    body.append("")

    # Button Hover
    body.append("    /// <summary>Punch scale for button hover feedback.</summary>")
    body.append("    public static Tween ButtonHover(RectTransform button, float strength = 0.1f, float duration = 0.2f)")
    body.append("    {")
    body.append("        return Tween.PunchLocalScale(button, strength: new Vector3(strength, strength, 0), duration: duration);")
    body.append("    }")
    body.append("")

    # Notification Popup
    body.append("    /// <summary>Slide-in + fade notification popup.</summary>")
    body.append("    public static Sequence NotificationPopup(RectTransform panel, CanvasGroup canvasGroup, float slideDistance = 100f, float duration = 0.5f)")
    body.append("    {")
    body.append("        var startPos = panel.anchoredPosition;")
    body.append("        panel.anchoredPosition = startPos + Vector2.up * slideDistance;")
    body.append("        canvasGroup.alpha = 0f;")
    body.append("        return Sequence.Create()")
    body.append("            .Group(Tween.UIAnchoredPosition(panel, endValue: startPos, duration: duration, ease: Ease.OutBack))")
    body.append("            .Group(Tween.Alpha(canvasGroup, endValue: 1f, duration: duration * 0.5f, ease: Ease.OutCubic));")
    body.append("    }")
    body.append("")

    # Screen Shake
    body.append("    /// <summary>Camera/UI shake effect using PrimeTween.</summary>")
    body.append("    public static Tween ScreenShake(RectTransform target, float strength = 10f, float duration = 0.3f)")
    body.append("    {")
    body.append("        return Tween.ShakeLocalPosition(target, strength: new Vector3(strength, strength, 0), duration: duration);")
    body.append("    }")
    body.append("")

    # Damage Flash
    body.append("    /// <summary>Red flash overlay for damage feedback.</summary>")
    body.append("    public static Sequence DamageFlash(CanvasGroup flashOverlay, float intensity = 0.6f, float duration = 0.15f)")
    body.append("    {")
    body.append("        flashOverlay.alpha = 0f;")
    body.append("        return Sequence.Create()")
    body.append("            .Chain(Tween.Alpha(flashOverlay, endValue: intensity, duration: duration * 0.3f, ease: Ease.OutCubic))")
    body.append("            .Chain(Tween.Alpha(flashOverlay, endValue: 0f, duration: duration * 0.7f, ease: Ease.InQuad));")
    body.append("    }")
    body.append("")

    # Item Pickup
    body.append("    /// <summary>Bounce + glow effect for item pickup notification.</summary>")
    body.append("    public static Sequence ItemPickup(RectTransform icon, CanvasGroup canvasGroup, float duration = 0.6f)")
    body.append("    {")
    body.append("        icon.localScale = Vector3.zero;")
    body.append("        canvasGroup.alpha = 0f;")
    body.append("        return Sequence.Create()")
    body.append("            .Group(Tween.Scale(icon, endValue: Vector3.one, duration: duration * 0.5f, ease: Ease.OutBack))")
    body.append("            .Group(Tween.Alpha(canvasGroup, endValue: 1f, duration: duration * 0.3f, ease: Ease.OutCubic))")
    body.append("            .Chain(Tween.PunchLocalScale(icon, strength: new Vector3(0.2f, 0.2f, 0), duration: duration * 0.5f));")
    body.append("    }")
    body.append("")

    # Level Up
    body.append("    /// <summary>Grand scale-up + flash for level up celebration.</summary>")
    body.append("    public static Sequence LevelUp(RectTransform panel, CanvasGroup canvasGroup, float duration = 0.8f)")
    body.append("    {")
    body.append("        panel.localScale = Vector3.one * 2f;")
    body.append("        canvasGroup.alpha = 0f;")
    body.append("        return Sequence.Create()")
    body.append("            .Group(Tween.Scale(panel, endValue: Vector3.one, duration: duration * 0.4f, ease: Ease.OutBack))")
    body.append("            .Group(Tween.Alpha(canvasGroup, endValue: 1f, duration: duration * 0.3f, ease: Ease.OutCubic))")
    body.append("            .Chain(Tween.PunchLocalScale(panel, strength: new Vector3(0.15f, 0.15f, 0), duration: duration * 0.6f));")
    body.append("    }")

    body.append("}")

    if namespace:
        lines.extend(_wrap_namespace(body, namespace))
    else:
        lines.extend(body)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PIPE-10: TMP font asset creation editor script
# ---------------------------------------------------------------------------


def generate_tmp_font_asset_script(
    font_path: str = "Assets/Fonts/Cinzel-Regular.ttf",
    output_path: str = "Assets/Fonts/Generated",
    sampling_size: int = 48,
    atlas_width: int = 1024,
    atlas_height: int = 1024,
    character_set: Optional[str] = None,
    namespace: str = "",
) -> str:
    """Generate editor script for TMP font asset creation.

    Uses TMP_FontAsset.CreateFontAsset with configurable atlas settings,
    SDF rendering, and character sets including ASCII 32-126 + extended Latin.

    Args:
        font_path: Path to the source .ttf/.otf font file.
        output_path: Directory for generated font asset.
        sampling_size: Font sampling size in pixels.
        atlas_width: Atlas texture width.
        atlas_height: Atlas texture height.
        character_set: Custom character set string (defaults to ASCII + extended Latin).
        namespace: Optional C# namespace.

    Returns:
        C# editor script source string.
    """
    safe_font_path = sanitize_cs_string(font_path)
    safe_output_path = sanitize_cs_string(output_path)

    # Default character set: ASCII 32-126 + common extended Latin
    default_chars = (
        " !\\\"#$%&'()*+,-./0123456789:;<=>?@"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\\\]^_`"
        "abcdefghijklmnopqrstuvwxyz{|}~"
        # Extended Latin (accented characters)
        "\\u00C0\\u00C1\\u00C2\\u00C3\\u00C4\\u00C5"  # A-accents
        "\\u00C8\\u00C9\\u00CA\\u00CB"  # E-accents
        "\\u00CC\\u00CD\\u00CE\\u00CF"  # I-accents
        "\\u00D1"  # N-tilde
        "\\u00D2\\u00D3\\u00D4\\u00D5\\u00D6"  # O-accents
        "\\u00D9\\u00DA\\u00DB\\u00DC"  # U-accents
        "\\u00E0\\u00E1\\u00E2\\u00E3\\u00E4\\u00E5"  # a-accents
        "\\u00E8\\u00E9\\u00EA\\u00EB"  # e-accents
        "\\u00EC\\u00ED\\u00EE\\u00EF"  # i-accents
        "\\u00F1"  # n-tilde
        "\\u00F2\\u00F3\\u00F4\\u00F5\\u00F6"  # o-accents
        "\\u00F9\\u00FA\\u00FB\\u00FC"  # u-accents
        "\\u00DF\\u00FF"  # sharp-s, y-umlaut
    )
    char_set = sanitize_cs_string(character_set) if character_set else default_chars

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using TMPro;")
    lines.append("using TMPro.EditorUtilities;")
    lines.append("using UnityEngine.TextCore.LowLevel;")
    lines.append("using System.IO;")
    lines.append("")

    body: list[str] = []
    body.append("public class VB_FontAssetGenerator : EditorWindow")
    body.append("{")
    body.append(f'    private string _fontPath = "{safe_font_path}";')
    body.append(f'    private string _outputPath = "{safe_output_path}";')
    body.append(f"    private int _samplingSize = {sampling_size};")
    body.append(f"    private int _atlasWidth = {atlas_width};")
    body.append(f"    private int _atlasHeight = {atlas_height};")
    body.append("")
    body.append("    [SerializeField] private TMP_FontAsset[] _fallbackFonts;")
    body.append("")
    body.append('    [MenuItem("VeilBreakers/Fonts/Generate Font Asset")]')
    body.append("    public static void ShowWindow()")
    body.append("    {")
    body.append('        GetWindow<VB_FontAssetGenerator>("Font Asset Generator");')
    body.append("    }")
    body.append("")
    body.append('    [MenuItem("VeilBreakers/Fonts/Generate Font Asset Quick")]')
    body.append("    public static void GenerateQuick()")
    body.append("    {")
    body.append("        var generator = CreateInstance<VB_FontAssetGenerator>();")
    body.append("        generator.GenerateFontAsset();")
    body.append("        DestroyImmediate(generator);")
    body.append("    }")
    body.append("")
    body.append("    private void GenerateFontAsset()")
    body.append("    {")
    body.append("        // Load source font")
    body.append("        var sourceFont = AssetDatabase.LoadAssetAtPath<Font>(_fontPath);")
    body.append("        if (sourceFont == null)")
    body.append("        {")
    body.append('            Debug.LogError($"Font not found at {_fontPath}");')
    body.append("            return;")
    body.append("        }")
    body.append("")
    body.append("        // Create TMP font asset with SDF rendering")
    body.append("        var fontAsset = TMP_FontAsset.CreateFontAsset(")
    body.append("            sourceFont,")
    body.append("            _samplingSize,")
    body.append("            5,  // padding")
    body.append("            GlyphRenderMode.SDFAA,")
    body.append("            _atlasWidth,")
    body.append("            _atlasHeight")
    body.append("        );")
    body.append("")
    body.append("        if (fontAsset == null)")
    body.append("        {")
    body.append('            Debug.LogError("Failed to create TMP font asset.");')
    body.append("            return;")
    body.append("        }")
    body.append("")
    body.append("        // Add character set")
    body.append(f'        string characterSet = "{char_set}";')
    body.append("        bool success = fontAsset.TryAddCharacters(characterSet);")
    body.append("        if (!success)")
    body.append('            Debug.LogWarning("Some characters could not be added to the font asset.");')
    body.append("")
    body.append("        // Setup fallback chain")
    body.append("        if (_fallbackFonts != null && _fallbackFonts.Length > 0)")
    body.append("        {")
    body.append("            fontAsset.fallbackFontAssetTable = new System.Collections.Generic.List<TMP_FontAsset>();")
    body.append("            foreach (var fallback in _fallbackFonts)")
    body.append("            {")
    body.append("                if (fallback != null)")
    body.append("                    fontAsset.fallbackFontAssetTable.Add(fallback);")
    body.append("            }")
    body.append("        }")
    body.append("")
    body.append("        // Ensure output directory exists")
    body.append("        if (!Directory.Exists(_outputPath))")
    body.append("            Directory.CreateDirectory(_outputPath);")
    body.append("")
    body.append("        // Save asset")
    body.append('        string assetPath = $"{_outputPath}/{sourceFont.name}_SDF.asset";')
    body.append("        AssetDatabase.CreateAsset(fontAsset, assetPath);")
    body.append("        AssetDatabase.SaveAssets();")
    body.append('        Debug.Log($"Font asset created at {assetPath}");')
    body.append("    }")
    body.append("}")

    if namespace:
        lines.extend(_wrap_namespace(body, namespace))
    else:
        lines.extend(body)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PIPE-10: TMP component setup editor script
# ---------------------------------------------------------------------------


def generate_tmp_component_script(
    name: str = "TMPSetup",
    font_asset_path: str = "",
    font_size: int = 36,
    color: Optional[list[float]] = None,
    rich_text: bool = True,
    auto_sizing: bool = False,
    min_size: int = 18,
    max_size: int = 72,
    namespace: str = "",
) -> str:
    """Generate editor script that configures TextMeshProUGUI components.

    Creates or configures TMP components on selected GameObjects with
    specified font asset, size, color, rich text, and auto-sizing settings.

    Args:
        name: Identifier name for the setup.
        font_asset_path: Path to the TMP font asset.
        font_size: Default font size.
        color: RGBA color values (defaults to white).
        rich_text: Enable rich text parsing.
        auto_sizing: Enable auto-sizing.
        min_size: Minimum auto-size.
        max_size: Maximum auto-size.
        namespace: Optional C# namespace.

    Returns:
        C# editor script source string.
    """
    safe_name = sanitize_cs_identifier(name)
    safe_font_path = sanitize_cs_string(font_asset_path) if font_asset_path else ""
    rgba = color or [1.0, 1.0, 1.0, 1.0]
    r, g, b, a = rgba[0], rgba[1], rgba[2], rgba[3]

    lines: list[str] = []
    lines.append("using UnityEngine;")
    lines.append("using UnityEditor;")
    lines.append("using TMPro;")
    lines.append("")

    body: list[str] = []
    body.append(f"public class VB_{safe_name}Configurator : EditorWindow")
    body.append("{")
    body.append(f"    [SerializeField] private TMP_FontAsset _fontAsset;")
    body.append(f"    [SerializeField] private TMP_FontAsset[] _fallbackFonts;")
    body.append(f"    [SerializeField] private int _fontSize = {font_size};")
    body.append(f"    [SerializeField] private Color _fontColor = new Color({r}f, {g}f, {b}f, {a}f);")
    body.append(f"    [SerializeField] private bool _richText = {str(rich_text).lower()};")
    body.append(f"    [SerializeField] private bool _autoSizing = {str(auto_sizing).lower()};")
    body.append(f"    [SerializeField] private int _minSize = {min_size};")
    body.append(f"    [SerializeField] private int _maxSize = {max_size};")
    body.append(f"    [SerializeField] private TextAlignmentOptions _alignment = TextAlignmentOptions.Center;")
    body.append(f"    [SerializeField] private TextOverflowModes _overflowMode = TextOverflowModes.Ellipsis;")
    body.append(f"    [SerializeField] private bool _wordWrapping = true;")
    body.append("")
    body.append('    [MenuItem("VeilBreakers/UI/Setup TMP Components")]')
    body.append("    public static void ShowWindow()")
    body.append("    {")
    body.append(f'        GetWindow<VB_{safe_name}Configurator>("TMP Component Setup");')
    body.append("    }")
    body.append("")
    body.append("    private void OnGUI()")
    body.append("    {")
    body.append('        GUILayout.Label("TMP Component Configuration", EditorStyles.boldLabel);')
    body.append("        EditorGUILayout.Space();")
    body.append("")
    body.append('        _fontAsset = (TMP_FontAsset)EditorGUILayout.ObjectField("Font Asset", _fontAsset, typeof(TMP_FontAsset), false);')
    body.append('        _fontSize = EditorGUILayout.IntField("Font Size", _fontSize);')
    body.append('        _fontColor = EditorGUILayout.ColorField("Color", _fontColor);')
    body.append('        _richText = EditorGUILayout.Toggle("Rich Text", _richText);')
    body.append('        _autoSizing = EditorGUILayout.Toggle("Auto Sizing", _autoSizing);')
    body.append("")
    body.append("        if (_autoSizing)")
    body.append("        {")
    body.append("            EditorGUI.indentLevel++;")
    body.append('            _minSize = EditorGUILayout.IntField("Min Size", _minSize);')
    body.append('            _maxSize = EditorGUILayout.IntField("Max Size", _maxSize);')
    body.append("            EditorGUI.indentLevel--;")
    body.append("        }")
    body.append("")
    body.append('        _alignment = (TextAlignmentOptions)EditorGUILayout.EnumPopup("Alignment", _alignment);')
    body.append('        _overflowMode = (TextOverflowModes)EditorGUILayout.EnumPopup("Overflow", _overflowMode);')
    body.append('        _wordWrapping = EditorGUILayout.Toggle("Word Wrapping", _wordWrapping);')
    body.append("")
    body.append("        EditorGUILayout.Space();")
    body.append("")
    body.append('        if (GUILayout.Button("Apply to Selected GameObjects"))')
    body.append("        {")
    body.append("            ApplyToSelection();")
    body.append("        }")
    body.append("    }")
    body.append("")
    body.append("    private void ApplyToSelection()")
    body.append("    {")
    body.append("        var selectedObjects = Selection.gameObjects;")
    body.append("        if (selectedObjects.Length == 0)")
    body.append("        {")
    body.append('            Debug.LogWarning("No GameObjects selected.");')
    body.append("            return;")
    body.append("        }")
    body.append("")
    body.append("        int configured = 0;")
    body.append("        foreach (var obj in selectedObjects)")
    body.append("        {")
    body.append('            Undo.RecordObject(obj, "Configure TMP Component");')
    body.append("")
    body.append("            var tmp = obj.GetComponent<TextMeshProUGUI>();")
    body.append("            if (tmp == null)")
    body.append("                tmp = Undo.AddComponent<TextMeshProUGUI>(obj);")
    body.append("")
    body.append("            // Font asset")
    body.append("            if (_fontAsset != null)")
    body.append("                tmp.font = _fontAsset;")
    body.append("")
    body.append("            // Font size")
    body.append("            tmp.fontSize = _fontSize;")
    body.append("            tmp.color = _fontColor;")
    body.append("            tmp.richText = _richText;")
    body.append("")
    body.append("            // Auto sizing")
    body.append("            tmp.enableAutoSizing = _autoSizing;")
    body.append("            if (_autoSizing)")
    body.append("            {")
    body.append("                tmp.fontSizeMin = _minSize;")
    body.append("                tmp.fontSizeMax = _maxSize;")
    body.append("            }")
    body.append("")
    body.append("            // Alignment and overflow")
    body.append("            tmp.alignment = _alignment;")
    body.append("            tmp.overflowMode = _overflowMode;")
    body.append("            tmp.enableWordWrapping = _wordWrapping;")
    body.append("")
    body.append("            // Fallback font chain")
    body.append("            if (_fallbackFonts != null && _fallbackFonts.Length > 0 && tmp.font != null)")
    body.append("            {")
    body.append("                tmp.font.fallbackFontAssetTable = new System.Collections.Generic.List<TMP_FontAsset>();")
    body.append("                foreach (var fallback in _fallbackFonts)")
    body.append("                {")
    body.append("                    if (fallback != null)")
    body.append("                        tmp.font.fallbackFontAssetTable.Add(fallback);")
    body.append("                }")
    body.append("            }")
    body.append("")
    body.append("            EditorUtility.SetDirty(obj);")
    body.append("            configured++;")
    body.append("        }")
    body.append("")
    body.append('        Debug.Log($"Configured {configured} TMP components.");')
    body.append("    }")
    body.append("}")

    if namespace:
        lines.extend(_wrap_namespace(body, namespace))
    else:
        lines.extend(body)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Rarity VFX data (EQUIP-07)
# ---------------------------------------------------------------------------

RARITY_VFX = {
    "Common": {"color": [0.5, 0.5, 0.5, 1.0], "glow": 0.0, "particles": 0},
    "Uncommon": {"color": [0.2, 0.8, 0.2, 1.0], "glow": 0.3, "particles": 5},
    "Rare": {"color": [0.2, 0.4, 1.0, 1.0], "glow": 0.6, "particles": 15},
    "Epic": {"color": [0.6, 0.2, 0.9, 1.0], "glow": 0.8, "particles": 30},
    "Legendary": {"color": [1.0, 0.8, 0.1, 1.0], "glow": 1.2, "particles": 60},
}


# ---------------------------------------------------------------------------
# UIX-02: Tutorial System
# ---------------------------------------------------------------------------


def generate_tutorial_system_script(
    name: str = "Tutorial",
    steps: list[dict] | None = None,
    namespace: str = "",
) -> tuple[str, str, str, str]:
    """Generate tutorial system with step-based state machine.

    Returns a tuple of (data_so_cs, manager_cs, uxml, uss).

    The SO holds per-step data (title, description, highlight rect, required
    action).  The manager MonoBehaviour drives a step-based state machine with
    tooltip overlays and highlight rects.  PrimeTween handles fade transitions.

    Args:
        name: Base name for the tutorial system.
        steps: Optional preset steps (unused in template -- runtime configured).
        namespace: Optional C# namespace.
    """
    safe_name = sanitize_cs_identifier(name)

    # --- Tutorial Step ScriptableObject ---
    so_body: list[str] = []
    so_body.append("using System;")
    so_body.append("using UnityEngine;")
    so_body.append("")
    so_body.append("/// <summary>")
    so_body.append("/// Data for a single tutorial step.")
    so_body.append("/// Generated by VeilBreakers MCP toolkit.")
    so_body.append("/// </summary>")
    so_body.append('[CreateAssetMenu(fileName = "New' + safe_name + 'Step", menuName = "VeilBreakers/Tutorial/Step")]')
    so_body.append("public class " + safe_name + "StepData : ScriptableObject")
    so_body.append("{")
    so_body.append('    [Header("Step Content")]')
    so_body.append("    public string stepTitle;")
    so_body.append("    [TextArea(2, 5)]")
    so_body.append("    public string stepDescription;")
    so_body.append("")
    so_body.append('    [Header("Highlight Target")]')
    so_body.append("    public string highlightObjectPath;")
    so_body.append("    public Rect highlightRect;")
    so_body.append("")
    so_body.append('    [Header("Progression")]')
    so_body.append("    public string requiredAction;")
    so_body.append("    public bool isOptional;")
    so_body.append("}")

    so_lines: list[str] = []
    if namespace:
        so_lines.extend(_wrap_namespace(so_body, namespace))
    else:
        so_lines.extend(so_body)
    data_so_cs = "\n".join(so_lines)

    # --- Tutorial Manager MonoBehaviour ---
    mgr_body: list[str] = []
    mgr_body.append("using System;")
    mgr_body.append("using System.Collections.Generic;")
    mgr_body.append("using UnityEngine;")
    mgr_body.append("using UnityEngine.UIElements;")
    mgr_body.append("using PrimeTween;")
    mgr_body.append("")
    mgr_body.append("/// <summary>")
    mgr_body.append("/// Step-based tutorial state machine with tooltip overlays and highlight rects.")
    mgr_body.append("/// Uses PrimeTween for fade transitions between steps.")
    mgr_body.append("/// Generated by VeilBreakers MCP toolkit.")
    mgr_body.append("/// </summary>")
    mgr_body.append("public class " + safe_name + "Manager : MonoBehaviour")
    mgr_body.append("{")
    mgr_body.append('    [Header("Tutorial Steps")]')
    mgr_body.append("    [SerializeField] private List<" + safe_name + "StepData> _steps = new List<" + safe_name + "StepData>();")
    mgr_body.append("")
    mgr_body.append('    [Header("UI References")]')
    mgr_body.append("    [SerializeField] private UIDocument _uiDocument;")
    mgr_body.append("")
    mgr_body.append("    private int _currentStepIndex = -1;")
    mgr_body.append("    private VisualElement _root;")
    mgr_body.append("    private VisualElement _overlay;")
    mgr_body.append("    private VisualElement _tooltipContainer;")
    mgr_body.append("    private Label _titleLabel;")
    mgr_body.append("    private Label _descriptionLabel;")
    mgr_body.append("    private Label _stepCounterLabel;")
    mgr_body.append("    private VisualElement _highlightFrame;")
    mgr_body.append("    private Button _skipButton;")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Fired when the entire tutorial completes.</summary>")
    mgr_body.append("    public event Action OnTutorialComplete;")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Fired when a step changes. Passes new step index.</summary>")
    mgr_body.append("    public event Action<int> OnStepChanged;")
    mgr_body.append("")
    mgr_body.append("    private void Awake()")
    mgr_body.append("    {")
    mgr_body.append("        if (_uiDocument != null)")
    mgr_body.append("        {")
    mgr_body.append("            _root = _uiDocument.rootVisualElement;")
    mgr_body.append('            _overlay = _root.Q<VisualElement>("tutorial-overlay");')
    mgr_body.append('            _tooltipContainer = _root.Q<VisualElement>("tooltip-container");')
    mgr_body.append('            _titleLabel = _root.Q<Label>("tutorial-title");')
    mgr_body.append('            _descriptionLabel = _root.Q<Label>("tutorial-description");')
    mgr_body.append('            _stepCounterLabel = _root.Q<Label>("step-counter");')
    mgr_body.append('            _highlightFrame = _root.Q<VisualElement>("highlight-frame");')
    mgr_body.append('            _skipButton = _root.Q<Button>("skip-button");')
    mgr_body.append("            if (_skipButton != null)")
    mgr_body.append("                _skipButton.clicked += SkipTutorial;")
    mgr_body.append("        }")
    mgr_body.append("        HideOverlay();")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Begin the tutorial from step 0.</summary>")
    mgr_body.append("    public void StartTutorial()")
    mgr_body.append("    {")
    mgr_body.append("        if (_steps == null || _steps.Count == 0) return;")
    mgr_body.append("        _currentStepIndex = -1;")
    mgr_body.append("        ShowOverlay();")
    mgr_body.append("        AdvanceStep();")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Advance to the next tutorial step.</summary>")
    mgr_body.append("    public void AdvanceStep()")
    mgr_body.append("    {")
    mgr_body.append("        _currentStepIndex++;")
    mgr_body.append("        if (_currentStepIndex >= _steps.Count)")
    mgr_body.append("        {")
    mgr_body.append("            CompleteTutorial();")
    mgr_body.append("            return;")
    mgr_body.append("        }")
    mgr_body.append("        var step = _steps[_currentStepIndex];")
    mgr_body.append("        DisplayStep(step);")
    mgr_body.append("        OnStepChanged?.Invoke(_currentStepIndex);")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Skip the tutorial entirely.</summary>")
    mgr_body.append("    public void SkipTutorial()")
    mgr_body.append("    {")
    mgr_body.append("        CompleteTutorial();")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Called when an action is triggered.</summary>")
    mgr_body.append("    public void OnActionTriggered(string actionName)")
    mgr_body.append("    {")
    mgr_body.append("        if (_currentStepIndex < 0 || _currentStepIndex >= _steps.Count) return;")
    mgr_body.append("        var step = _steps[_currentStepIndex];")
    mgr_body.append("        if (step.requiredAction == actionName || step.isOptional)")
    mgr_body.append("            AdvanceStep();")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    private void DisplayStep(" + safe_name + "StepData step)")
    mgr_body.append("    {")
    mgr_body.append("        if (_titleLabel != null) _titleLabel.text = step.stepTitle;")
    mgr_body.append("        if (_descriptionLabel != null) _descriptionLabel.text = step.stepDescription;")
    mgr_body.append("        if (_stepCounterLabel != null)")
    mgr_body.append('            _stepCounterLabel.text = $"Step {_currentStepIndex + 1} / {_steps.Count}";')
    mgr_body.append("        if (_highlightFrame != null)")
    mgr_body.append("        {")
    mgr_body.append("            _highlightFrame.style.left = step.highlightRect.x;")
    mgr_body.append("            _highlightFrame.style.top = step.highlightRect.y;")
    mgr_body.append("            _highlightFrame.style.width = step.highlightRect.width;")
    mgr_body.append("            _highlightFrame.style.height = step.highlightRect.height;")
    mgr_body.append("        }")
    mgr_body.append("        // Fade in tooltip with PrimeTween")
    mgr_body.append("        if (_tooltipContainer != null)")
    mgr_body.append("        {")
    mgr_body.append("            _tooltipContainer.style.opacity = 0f;")
    mgr_body.append("            Tween.Alpha(_tooltipContainer, 0f, 1f, 0.3f);")
    mgr_body.append("        }")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    private void CompleteTutorial()")
    mgr_body.append("    {")
    mgr_body.append("        if (_overlay != null)")
    mgr_body.append("            Tween.Alpha(_overlay, 1f, 0f, 0.5f);")
    mgr_body.append("        _currentStepIndex = -1;")
    mgr_body.append("        OnTutorialComplete?.Invoke();")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    private void ShowOverlay()")
    mgr_body.append("    {")
    mgr_body.append("        if (_overlay != null)")
    mgr_body.append("        {")
    mgr_body.append("            _overlay.style.display = DisplayStyle.Flex;")
    mgr_body.append("            Tween.Alpha(_overlay, 0f, 1f, 0.3f);")
    mgr_body.append("        }")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    private void HideOverlay()")
    mgr_body.append("    {")
    mgr_body.append("        if (_overlay != null)")
    mgr_body.append("            _overlay.style.display = DisplayStyle.None;")
    mgr_body.append("    }")
    mgr_body.append("}")

    mgr_lines: list[str] = []
    if namespace:
        mgr_lines.extend(_wrap_namespace(mgr_body, namespace))
    else:
        mgr_lines.extend(mgr_body)
    manager_cs = "\n".join(mgr_lines)

    # --- UXML ---
    uxml_lines: list[str] = []
    uxml_lines.append('<ui:UXML xmlns:ui="UnityEngine.UIElements" xmlns:uie="UnityEditor.UIElements">')
    uxml_lines.append('    <ui:VisualElement name="tutorial-overlay" class="tutorial-overlay">')
    uxml_lines.append('        <ui:VisualElement name="dim-background" class="dim-background" />')
    uxml_lines.append('        <ui:VisualElement name="highlight-frame" class="highlight-frame" />')
    uxml_lines.append('        <ui:VisualElement name="tooltip-container" class="tooltip-container">')
    uxml_lines.append('            <ui:Label name="tutorial-title" class="tutorial-title" text="Step Title" />')
    uxml_lines.append('            <ui:Label name="tutorial-description" class="tutorial-desc" text="Description" />')
    uxml_lines.append('            <ui:Label name="step-counter" class="step-counter" text="Step 1 / 5" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:Button name="skip-button" class="skip-button" text="Skip Tutorial" />')
    uxml_lines.append("    </ui:VisualElement>")
    uxml_lines.append("</ui:UXML>")
    uxml = "\n".join(uxml_lines)

    # --- USS ---
    uss_lines: list[str] = []
    uss_lines.append("/* VeilBreakers Tutorial Overlay - Dark Fantasy Theme */")
    uss_lines.append(".tutorial-overlay {")
    uss_lines.append("    position: absolute;")
    uss_lines.append("    width: 100%;")
    uss_lines.append("    height: 100%;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".dim-background {")
    uss_lines.append("    position: absolute;")
    uss_lines.append("    width: 100%;")
    uss_lines.append("    height: 100%;")
    uss_lines.append("    background-color: rgba(0, 0, 0, 0.7);")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".highlight-frame {")
    uss_lines.append("    position: absolute;")
    uss_lines.append("    border-width: 2px;")
    uss_lines.append("    border-color: rgb(212, 175, 55);")
    uss_lines.append("    border-radius: 4px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".tooltip-container {")
    uss_lines.append("    position: absolute;")
    uss_lines.append("    bottom: 120px;")
    uss_lines.append("    align-self: center;")
    uss_lines.append("    background-color: rgba(20, 15, 10, 0.95);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    border-color: rgb(212, 175, 55);")
    uss_lines.append("    border-radius: 8px;")
    uss_lines.append("    padding: 16px 24px;")
    uss_lines.append("    max-width: 400px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".tutorial-title {")
    uss_lines.append("    -unity-font-definition: url('project://Fonts/Cinzel-Bold.ttf');")
    uss_lines.append("    font-size: 22px;")
    uss_lines.append("    color: rgb(212, 175, 55);")
    uss_lines.append("    margin-bottom: 8px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".tutorial-desc {")
    uss_lines.append("    -unity-font-definition: url('project://Fonts/Cinzel-Regular.ttf');")
    uss_lines.append("    font-size: 16px;")
    uss_lines.append("    color: rgb(200, 190, 170);")
    uss_lines.append("    white-space: normal;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".step-counter {")
    uss_lines.append("    font-size: 12px;")
    uss_lines.append("    color: rgb(140, 130, 110);")
    uss_lines.append("    margin-top: 8px;")
    uss_lines.append("    -unity-text-align: middle-right;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".skip-button {")
    uss_lines.append("    position: absolute;")
    uss_lines.append("    top: 20px;")
    uss_lines.append("    right: 20px;")
    uss_lines.append("    background-color: rgba(40, 30, 20, 0.8);")
    uss_lines.append("    border-color: rgb(140, 110, 60);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    border-radius: 4px;")
    uss_lines.append("    color: rgb(200, 180, 140);")
    uss_lines.append("    -unity-font-definition: url('project://Fonts/Cinzel-Regular.ttf');")
    uss_lines.append("    font-size: 14px;")
    uss_lines.append("    padding: 6px 12px;")
    uss_lines.append("}")
    uss = "\n".join(uss_lines)

    return (data_so_cs, manager_cs, uxml, uss)


# ---------------------------------------------------------------------------
# ACC-01: Accessibility
# ---------------------------------------------------------------------------


def generate_accessibility_script(
    name: str = "Accessibility",
    namespace: str = "",
) -> tuple[str, str, str]:
    """Generate accessibility system with colorblind, subtitles, screen reader, motor.

    Returns a tuple of (settings_cs, shader_hlsl, renderer_feature_cs).

    The settings MonoBehaviour persists all preferences via PlayerPrefs and
    exposes public properties with change events.  The HLSL shader provides
    fullscreen colorblind simulation with 3 LMS matrices.  The renderer feature
    uses the URP RecordRenderGraph API for the fullscreen blit.

    Args:
        name: Base name for the accessibility system.
        namespace: Optional C# namespace.
    """
    safe_name = sanitize_cs_identifier(name)

    # --- Accessibility Settings MonoBehaviour ---
    settings_body: list[str] = []
    settings_body.append("using System;")
    settings_body.append("using UnityEngine;")
    settings_body.append("")
    settings_body.append("/// <summary>")
    settings_body.append("/// Accessibility settings manager with PlayerPrefs persistence.")
    settings_body.append("/// Covers colorblind modes, subtitle scaling, screen reader tags, and motor accessibility.")
    settings_body.append("/// Generated by VeilBreakers MCP toolkit.")
    settings_body.append("/// </summary>")
    settings_body.append("public enum ColorblindMode")
    settings_body.append("{")
    settings_body.append("    None = 0,")
    settings_body.append("    Protanopia = 1,")
    settings_body.append("    Deuteranopia = 2,")
    settings_body.append("    Tritanopia = 3")
    settings_body.append("}")
    settings_body.append("")
    settings_body.append("public class " + safe_name + "Settings : MonoBehaviour")
    settings_body.append("{")
    settings_body.append('    private const string KEY_COLORBLIND = "Accessibility_ColorblindMode";')
    settings_body.append('    private const string KEY_SUBTITLE_SCALE = "Accessibility_SubtitleScale";')
    settings_body.append('    private const string KEY_SCREEN_READER = "Accessibility_ScreenReader";')
    settings_body.append('    private const string KEY_TOGGLE_VS_HOLD = "Accessibility_ToggleVsHold";')
    settings_body.append('    private const string KEY_INPUT_TIMING = "Accessibility_InputTiming";')
    settings_body.append("")
    settings_body.append('    [Header("Colorblind")]')
    settings_body.append("    [SerializeField] private ColorblindMode _colorblindMode = ColorblindMode.None;")
    settings_body.append("")
    settings_body.append('    [Header("Subtitles")]')
    settings_body.append("    [SerializeField, Range(1f, 3f)] private float _subtitleScale = 1.0f;")
    settings_body.append("")
    settings_body.append('    [Header("Screen Reader")]')
    settings_body.append("    [SerializeField] private bool _screenReaderEnabled;")
    settings_body.append("")
    settings_body.append('    [Header("Motor Accessibility")]')
    settings_body.append("    [SerializeField] private bool _useToggleInsteadOfHold;")
    settings_body.append("    [SerializeField, Range(0.5f, 2.0f)] private float _inputTimingMultiplier = 1.0f;")
    settings_body.append("")
    settings_body.append("    /// <summary>Fired when any accessibility setting changes.</summary>")
    settings_body.append("    public event Action OnSettingsChanged;")
    settings_body.append("")
    settings_body.append("    /// <summary>Current colorblind mode.</summary>")
    settings_body.append("    public ColorblindMode CurrentColorblindMode")
    settings_body.append("    {")
    settings_body.append("        get => _colorblindMode;")
    settings_body.append("        set")
    settings_body.append("        {")
    settings_body.append("            _colorblindMode = value;")
    settings_body.append("            PlayerPrefs.SetInt(KEY_COLORBLIND, (int)value);")
    settings_body.append("            PlayerPrefs.Save();")
    settings_body.append("            OnSettingsChanged?.Invoke();")
    settings_body.append("        }")
    settings_body.append("    }")
    settings_body.append("")
    settings_body.append("    /// <summary>Subtitle text scale (1.0 to 3.0).</summary>")
    settings_body.append("    public float SubtitleScale")
    settings_body.append("    {")
    settings_body.append("        get => _subtitleScale;")
    settings_body.append("        set")
    settings_body.append("        {")
    settings_body.append("            _subtitleScale = Mathf.Clamp(value, 1f, 3f);")
    settings_body.append("            PlayerPrefs.SetFloat(KEY_SUBTITLE_SCALE, _subtitleScale);")
    settings_body.append("            PlayerPrefs.Save();")
    settings_body.append("            OnSettingsChanged?.Invoke();")
    settings_body.append("        }")
    settings_body.append("    }")
    settings_body.append("")
    settings_body.append("    /// <summary>Whether screen reader accessibility tags are enabled.</summary>")
    settings_body.append("    public bool ScreenReaderEnabled")
    settings_body.append("    {")
    settings_body.append("        get => _screenReaderEnabled;")
    settings_body.append("        set")
    settings_body.append("        {")
    settings_body.append("            _screenReaderEnabled = value;")
    settings_body.append("            PlayerPrefs.SetInt(KEY_SCREEN_READER, value ? 1 : 0);")
    settings_body.append("            PlayerPrefs.Save();")
    settings_body.append("            OnSettingsChanged?.Invoke();")
    settings_body.append("        }")
    settings_body.append("    }")
    settings_body.append("")
    settings_body.append("    /// <summary>Use toggle instead of hold for actions (motor accessibility).</summary>")
    settings_body.append("    public bool UseToggleInsteadOfHold")
    settings_body.append("    {")
    settings_body.append("        get => _useToggleInsteadOfHold;")
    settings_body.append("        set")
    settings_body.append("        {")
    settings_body.append("            _useToggleInsteadOfHold = value;")
    settings_body.append("            PlayerPrefs.SetInt(KEY_TOGGLE_VS_HOLD, value ? 1 : 0);")
    settings_body.append("            PlayerPrefs.Save();")
    settings_body.append("            OnSettingsChanged?.Invoke();")
    settings_body.append("        }")
    settings_body.append("    }")
    settings_body.append("")
    settings_body.append("    /// <summary>Input timing multiplier (0.5 to 2.0) for motor accessibility.</summary>")
    settings_body.append("    public float InputTimingMultiplier")
    settings_body.append("    {")
    settings_body.append("        get => _inputTimingMultiplier;")
    settings_body.append("        set")
    settings_body.append("        {")
    settings_body.append("            _inputTimingMultiplier = Mathf.Clamp(value, 0.5f, 2.0f);")
    settings_body.append("            PlayerPrefs.SetFloat(KEY_INPUT_TIMING, _inputTimingMultiplier);")
    settings_body.append("            PlayerPrefs.Save();")
    settings_body.append("            OnSettingsChanged?.Invoke();")
    settings_body.append("        }")
    settings_body.append("    }")
    settings_body.append("")
    settings_body.append("    /// <summary>Apply screen reader labels to a UI element.</summary>")
    settings_body.append("    public void ApplyScreenReaderLabel(GameObject uiElement, string label)")
    settings_body.append("    {")
    settings_body.append("        if (!_screenReaderEnabled || uiElement == null) return;")
    settings_body.append("        uiElement.name = label;")
    settings_body.append("    }")
    settings_body.append("")
    settings_body.append("    private void Awake()")
    settings_body.append("    {")
    settings_body.append("        LoadSettings();")
    settings_body.append("    }")
    settings_body.append("")
    settings_body.append("    private void LoadSettings()")
    settings_body.append("    {")
    settings_body.append("        _colorblindMode = (ColorblindMode)PlayerPrefs.GetInt(KEY_COLORBLIND, 0);")
    settings_body.append("        _subtitleScale = PlayerPrefs.GetFloat(KEY_SUBTITLE_SCALE, 1.0f);")
    settings_body.append("        _screenReaderEnabled = PlayerPrefs.GetInt(KEY_SCREEN_READER, 0) == 1;")
    settings_body.append("        _useToggleInsteadOfHold = PlayerPrefs.GetInt(KEY_TOGGLE_VS_HOLD, 0) == 1;")
    settings_body.append("        _inputTimingMultiplier = PlayerPrefs.GetFloat(KEY_INPUT_TIMING, 1.0f);")
    settings_body.append("    }")
    settings_body.append("}")

    settings_lines: list[str] = []
    if namespace:
        settings_lines.extend(_wrap_namespace(settings_body, namespace))
    else:
        settings_lines.extend(settings_body)
    settings_cs = "\n".join(settings_lines)

    # --- Colorblind Simulation Shader (HLSL) ---
    shader_lines: list[str] = []
    shader_lines.append('Shader "VeilBreakers/Accessibility/ColorblindFilter"')
    shader_lines.append("{")
    shader_lines.append("    Properties")
    shader_lines.append("    {")
    shader_lines.append('        _MainTex ("Main Texture", 2D) = "white" {}')
    shader_lines.append('        [IntRange] _ColorblindMode ("Colorblind Mode", Range(0, 3)) = 0')
    shader_lines.append("    }")
    shader_lines.append("")
    shader_lines.append("    SubShader")
    shader_lines.append("    {")
    shader_lines.append('        Tags { "RenderType"="Opaque" "RenderPipeline"="UniversalPipeline" }')
    shader_lines.append("")
    shader_lines.append("        Pass")
    shader_lines.append("        {")
    shader_lines.append('            Name "ColorblindFilter"')
    shader_lines.append("")
    shader_lines.append("            HLSLPROGRAM")
    shader_lines.append("            #pragma vertex Vert")
    shader_lines.append("            #pragma fragment Frag")
    shader_lines.append("")
    shader_lines.append('            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"')
    shader_lines.append('            #include "Packages/com.unity.render-pipelines.core/Runtime/Utilities/Blit.hlsl"')
    shader_lines.append("")
    shader_lines.append("            TEXTURE2D(_MainTex);")
    shader_lines.append("            SAMPLER(sampler_MainTex);")
    shader_lines.append("            int _ColorblindMode;")
    shader_lines.append("")
    shader_lines.append("            // Colorblind simulation matrices (LMS daltonization)")
    shader_lines.append("            // Protanopia: red-blind")
    shader_lines.append("            static const float3x3 Protanopia = float3x3(")
    shader_lines.append("                0.170556992, 0.829443014, 0.0,")
    shader_lines.append("                0.170556991, 0.829443008, 0.0,")
    shader_lines.append("                -0.004517144, 0.004517144, 1.0")
    shader_lines.append("            );")
    shader_lines.append("")
    shader_lines.append("            // Deuteranopia: green-blind")
    shader_lines.append("            static const float3x3 Deuteranopia = float3x3(")
    shader_lines.append("                0.33066007, 0.66933993, 0.0,")
    shader_lines.append("                0.33066007, 0.66933993, 0.0,")
    shader_lines.append("                -0.02785538, 0.02785538, 1.0")
    shader_lines.append("            );")
    shader_lines.append("")
    shader_lines.append("            // Tritanopia: blue-blind")
    shader_lines.append("            static const float3x3 Tritanopia = float3x3(")
    shader_lines.append("                1.0, 0.1273989, -0.1273989,")
    shader_lines.append("                0.0, 0.8739093, 0.1260907,")
    shader_lines.append("                0.0, 0.8739093, 0.1260907")
    shader_lines.append("            );")
    shader_lines.append("")
    shader_lines.append("            float3 SRGBToLinear(float3 srgb)")
    shader_lines.append("            {")
    shader_lines.append("                return pow(max(srgb, 0.0), 2.2);")
    shader_lines.append("            }")
    shader_lines.append("")
    shader_lines.append("            float3 LinearToSRGB(float3 linear)")
    shader_lines.append("            {")
    shader_lines.append("                return pow(max(linear, 0.0), 1.0 / 2.2);")
    shader_lines.append("            }")
    shader_lines.append("")
    shader_lines.append("            half4 Frag(Varyings input) : SV_Target")
    shader_lines.append("            {")
    shader_lines.append("                float2 uv = input.texcoord;")
    shader_lines.append("                half4 color = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, uv);")
    shader_lines.append("")
    shader_lines.append("                if (_ColorblindMode == 0) return color;")
    shader_lines.append("")
    shader_lines.append("                // Convert sRGB to linear before matrix multiply")
    shader_lines.append("                float3 linearColor = SRGBToLinear(color.rgb);")
    shader_lines.append("")
    shader_lines.append("                float3 result = linearColor;")
    shader_lines.append("                if (_ColorblindMode == 1)")
    shader_lines.append("                    result = mul(Protanopia, linearColor);")
    shader_lines.append("                else if (_ColorblindMode == 2)")
    shader_lines.append("                    result = mul(Deuteranopia, linearColor);")
    shader_lines.append("                else if (_ColorblindMode == 3)")
    shader_lines.append("                    result = mul(Tritanopia, linearColor);")
    shader_lines.append("")
    shader_lines.append("                // Convert back to sRGB after matrix multiply")
    shader_lines.append("                color.rgb = LinearToSRGB(result);")
    shader_lines.append("                return color;")
    shader_lines.append("            }")
    shader_lines.append("            ENDHLSL")
    shader_lines.append("        }")
    shader_lines.append("    }")
    shader_lines.append("}")
    shader_hlsl = "\n".join(shader_lines)

    # --- URP Renderer Feature (RecordRenderGraph API) ---
    feature_body: list[str] = []
    feature_body.append("using UnityEngine;")
    feature_body.append("using UnityEngine.Rendering;")
    feature_body.append("using UnityEngine.Rendering.Universal;")
    feature_body.append("using UnityEngine.Rendering.RenderGraphModule;")
    feature_body.append("")
    feature_body.append("/// <summary>")
    feature_body.append("/// URP ScriptableRendererFeature for fullscreen colorblind simulation.")
    feature_body.append("/// Uses RecordRenderGraph API (not legacy Execute).")
    feature_body.append("/// Generated by VeilBreakers MCP toolkit.")
    feature_body.append("/// </summary>")
    feature_body.append("public class " + safe_name + "ColorblindFeature : ScriptableRendererFeature")
    feature_body.append("{")
    feature_body.append("    [System.Serializable]")
    feature_body.append("    public class Settings")
    feature_body.append("    {")
    feature_body.append("        public Material colorblindMaterial;")
    feature_body.append("        public RenderPassEvent renderPassEvent = RenderPassEvent.AfterRenderingPostProcessing;")
    feature_body.append("    }")
    feature_body.append("")
    feature_body.append("    public Settings settings = new Settings();")
    feature_body.append("    private " + safe_name + "ColorblindPass _pass;")
    feature_body.append("")
    feature_body.append("    public override void Create()")
    feature_body.append("    {")
    feature_body.append("        _pass = new " + safe_name + "ColorblindPass(settings);")
    feature_body.append("        _pass.renderPassEvent = settings.renderPassEvent;")
    feature_body.append("    }")
    feature_body.append("")
    feature_body.append("    public override void AddRenderPasses(ScriptableRenderer renderer, ref RenderingData renderingData)")
    feature_body.append("    {")
    feature_body.append("        if (settings.colorblindMaterial != null)")
    feature_body.append("            renderer.EnqueuePass(_pass);")
    feature_body.append("    }")
    feature_body.append("")
    feature_body.append("    private class " + safe_name + "ColorblindPass : ScriptableRenderPass")
    feature_body.append("    {")
    feature_body.append("        private readonly Settings _settings;")
    feature_body.append("")
    feature_body.append("        public " + safe_name + "ColorblindPass(Settings settings)")
    feature_body.append("        {")
    feature_body.append("            _settings = settings;")
    feature_body.append("        }")
    feature_body.append("")
    feature_body.append("        public override void RecordRenderGraph(RenderGraph renderGraph, ContextContainer frameData)")
    feature_body.append("        {")
    feature_body.append("            if (_settings.colorblindMaterial == null) return;")
    feature_body.append("")
    feature_body.append("            var resourceData = frameData.Get<UniversalResourceData>();")
    feature_body.append("            var cameraColorHandle = resourceData.activeColorTexture;")
    feature_body.append("")
    feature_body.append("            var desc = renderGraph.GetTextureDesc(cameraColorHandle);")
    feature_body.append('            desc.name = "ColorblindTemp";')
    feature_body.append("            var tempHandle = renderGraph.CreateTexture(desc);")
    feature_body.append("")
    feature_body.append('            using (var builder = renderGraph.AddRasterRenderPass<PassData>("ColorblindFilter", out var passData))')
    feature_body.append("            {")
    feature_body.append("                passData.source = cameraColorHandle;")
    feature_body.append("                passData.material = _settings.colorblindMaterial;")
    feature_body.append("                builder.UseTexture(cameraColorHandle, AccessFlags.Read);")
    feature_body.append("                builder.SetRenderAttachment(tempHandle, 0, AccessFlags.Write);")
    feature_body.append("                builder.SetRenderFunc<PassData>((data, context) =>")
    feature_body.append("                {")
    feature_body.append("                    Blitter.BlitTexture(context.cmd, data.source, new Vector4(1, 1, 0, 0), data.material, 0);")
    feature_body.append("                });")
    feature_body.append("            }")
    feature_body.append("")
    feature_body.append('            using (var builder = renderGraph.AddRasterRenderPass<PassData>("ColorblindCopyBack", out var passData2))')
    feature_body.append("            {")
    feature_body.append("                passData2.source = tempHandle;")
    feature_body.append("                passData2.material = null;")
    feature_body.append("                builder.UseTexture(tempHandle, AccessFlags.Read);")
    feature_body.append("                builder.SetRenderAttachment(cameraColorHandle, 0, AccessFlags.Write);")
    feature_body.append("                builder.SetRenderFunc<PassData>((data, context) =>")
    feature_body.append("                {")
    feature_body.append("                    Blitter.BlitTexture(context.cmd, data.source, new Vector4(1, 1, 0, 0), 0);")
    feature_body.append("                });")
    feature_body.append("            }")
    feature_body.append("        }")
    feature_body.append("")
    feature_body.append("        private class PassData")
    feature_body.append("        {")
    feature_body.append("            public TextureHandle source;")
    feature_body.append("            public Material material;")
    feature_body.append("        }")
    feature_body.append("    }")
    feature_body.append("}")

    feature_lines: list[str] = []
    if namespace:
        feature_lines.extend(_wrap_namespace(feature_body, namespace))
    else:
        feature_lines.extend(feature_body)
    renderer_feature_cs = "\n".join(feature_lines)

    return (settings_cs, shader_hlsl, renderer_feature_cs)


# ---------------------------------------------------------------------------
# VB-09: Character Select
# ---------------------------------------------------------------------------


def generate_character_select_script(
    hero_paths: list[str] | None = None,
    namespace: str = "",
) -> tuple[str, str, str, str]:
    """Generate character selection screen with hero path carousel.

    Returns a tuple of (data_so_cs, manager_cs, uxml, uss).

    The SO holds hero path data (name, description, icon, stats).  The manager
    MonoBehaviour provides carousel navigation with PrimeTween Sequence
    animations, appearance customization, and validated name entry.

    Args:
        hero_paths: List of hero path names (default: 5 VB paths).
        namespace: Optional C# namespace.
    """
    if hero_paths is None:
        hero_paths = ["IRONBOUND", "FANGBORN", "VOIDTOUCHED", "UNCHAINED"]

    # --- Hero Path Data SO ---
    so_body: list[str] = []
    so_body.append("using UnityEngine;")
    so_body.append("")
    so_body.append("/// <summary>")
    so_body.append("/// ScriptableObject containing hero path data for character selection.")
    so_body.append("/// Generated by VeilBreakers MCP toolkit.")
    so_body.append("/// </summary>")
    so_body.append('[CreateAssetMenu(fileName = "NewPath", menuName = "VeilBreakers/Character/Hero Path")]')
    so_body.append("public class VB_PathData : ScriptableObject")
    so_body.append("{")
    so_body.append('    [Header("Identity")]')
    so_body.append("    public string pathName;")
    so_body.append("    [TextArea(2, 5)]")
    so_body.append("    public string description;")
    so_body.append("    public Sprite icon;")
    so_body.append("    public Color themeColor = Color.white;")
    so_body.append("")
    so_body.append('    [Header("Starting Abilities")]')
    so_body.append("    public string[] startingAbilities;")
    so_body.append("")
    so_body.append('    [Header("Base Stats")]')
    so_body.append("    public int baseStrength = 10;")
    so_body.append("    public int baseAgility = 10;")
    so_body.append("    public int baseIntelligence = 10;")
    so_body.append("}")

    so_lines: list[str] = []
    if namespace:
        so_lines.extend(_wrap_namespace(so_body, namespace))
    else:
        so_lines.extend(so_body)
    data_so_cs = "\n".join(so_lines)

    # --- Character Select Manager ---
    mgr_body: list[str] = []
    mgr_body.append("using System;")
    mgr_body.append("using System.Collections.Generic;")
    mgr_body.append("using UnityEngine;")
    mgr_body.append("using UnityEngine.UIElements;")
    mgr_body.append("using PrimeTween;")
    mgr_body.append("")
    mgr_body.append("/// <summary>")
    mgr_body.append("/// Character selection manager with hero path carousel, appearance customization,")
    mgr_body.append("/// and name entry. Uses PrimeTween Sequence for carousel animations.")
    mgr_body.append("/// Generated by VeilBreakers MCP toolkit.")
    mgr_body.append("/// </summary>")
    mgr_body.append("[Serializable]")
    mgr_body.append("public class CharacterAppearance")
    mgr_body.append("{")
    mgr_body.append("    public int skinColorIndex;")
    mgr_body.append("    public int hairStyleIndex;")
    mgr_body.append("    public int armorTintIndex;")
    mgr_body.append("}")
    mgr_body.append("")
    mgr_body.append("public class CharacterSelectManager : MonoBehaviour")
    mgr_body.append("{")
    mgr_body.append('    [Header("Hero Paths")]')
    mgr_body.append("    [SerializeField] private List<VB_PathData> _paths = new List<VB_PathData>();")
    mgr_body.append("")
    mgr_body.append('    [Header("Appearance Options")]')
    mgr_body.append('    [SerializeField] private string[] _skinColors = { "Pale", "Fair", "Olive", "Bronze", "Dark", "Ebony" };')
    mgr_body.append('    [SerializeField] private string[] _hairStyles = { "Short", "Long", "Braided", "Shaved", "Mohawk", "Ponytail" };')
    mgr_body.append('    [SerializeField] private string[] _armorTints = { "Iron", "Crimson", "Shadow", "Gold", "Emerald", "Azure" };')
    mgr_body.append("")
    mgr_body.append('    [Header("UI References")]')
    mgr_body.append("    [SerializeField] private UIDocument _uiDocument;")
    mgr_body.append("")
    mgr_body.append("    private int _currentPathIndex;")
    mgr_body.append('    private CharacterAppearance _appearance = new CharacterAppearance();')
    mgr_body.append('    private string _characterName = "";')
    mgr_body.append("")
    mgr_body.append("    private VisualElement _root;")
    mgr_body.append("    private VisualElement _carouselContainer;")
    mgr_body.append("    private Label _pathNameLabel;")
    mgr_body.append("    private Label _pathDescLabel;")
    mgr_body.append("    private Label _statsLabel;")
    mgr_body.append("    private Button _prevButton;")
    mgr_body.append("    private Button _nextButton;")
    mgr_body.append("    private Button _embarkButton;")
    mgr_body.append("    private TextField _nameInput;")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Fired when a hero path is selected in the carousel.</summary>")
    mgr_body.append("    public event Action<int> OnPathSelected;")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Fired when the player clicks Embark with valid data.</summary>")
    mgr_body.append("    public event Action<VB_PathData, CharacterAppearance, string> OnCharacterCreated;")
    mgr_body.append("")
    paths_str = ", ".join(['"' + p + '"' for p in hero_paths])
    mgr_body.append("    /// <summary>Default hero path names for reference.</summary>")
    mgr_body.append("    public static readonly string[] DefaultPaths = { " + paths_str + " };")
    mgr_body.append("")
    mgr_body.append("    private void Awake()")
    mgr_body.append("    {")
    mgr_body.append("        if (_uiDocument != null)")
    mgr_body.append("        {")
    mgr_body.append("            _root = _uiDocument.rootVisualElement;")
    mgr_body.append('            _carouselContainer = _root.Q<VisualElement>("carousel-container");')
    mgr_body.append('            _pathNameLabel = _root.Q<Label>("path-name");')
    mgr_body.append('            _pathDescLabel = _root.Q<Label>("path-description");')
    mgr_body.append('            _statsLabel = _root.Q<Label>("path-stats");')
    mgr_body.append('            _prevButton = _root.Q<Button>("prev-button");')
    mgr_body.append('            _nextButton = _root.Q<Button>("next-button");')
    mgr_body.append('            _embarkButton = _root.Q<Button>("embark-button");')
    mgr_body.append('            _nameInput = _root.Q<TextField>("name-input");')
    mgr_body.append("")
    mgr_body.append("            if (_prevButton != null) _prevButton.clicked += NavigatePrevious;")
    mgr_body.append("            if (_nextButton != null) _nextButton.clicked += NavigateNext;")
    mgr_body.append("            if (_embarkButton != null) _embarkButton.clicked += OnEmbarkClicked;")
    mgr_body.append("            if (_nameInput != null) _nameInput.RegisterValueChangedCallback(evt => _characterName = evt.newValue);")
    mgr_body.append("        }")
    mgr_body.append("        UpdateDisplay();")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Navigate to the previous hero path in the carousel.</summary>")
    mgr_body.append("    public void NavigatePrevious()")
    mgr_body.append("    {")
    mgr_body.append("        if (_paths.Count == 0) return;")
    mgr_body.append("        _currentPathIndex = (_currentPathIndex - 1 + _paths.Count) % _paths.Count;")
    mgr_body.append("        AnimateCarouselTransition(-1);")
    mgr_body.append("        OnPathSelected?.Invoke(_currentPathIndex);")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Navigate to the next hero path in the carousel.</summary>")
    mgr_body.append("    public void NavigateNext()")
    mgr_body.append("    {")
    mgr_body.append("        if (_paths.Count == 0) return;")
    mgr_body.append("        _currentPathIndex = (_currentPathIndex + 1) % _paths.Count;")
    mgr_body.append("        AnimateCarouselTransition(1);")
    mgr_body.append("        OnPathSelected?.Invoke(_currentPathIndex);")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Validate character name (3-20 chars, alphanumeric + spaces).</summary>")
    mgr_body.append("    public bool ValidateName(string name)")
    mgr_body.append("    {")
    mgr_body.append("        if (string.IsNullOrWhiteSpace(name)) return false;")
    mgr_body.append("        if (name.Length < 3 || name.Length > 20) return false;")
    mgr_body.append("        foreach (char c in name)")
    mgr_body.append("        {")
    mgr_body.append("            if (!char.IsLetterOrDigit(c) && c != ' ') return false;")
    mgr_body.append("        }")
    mgr_body.append("        return true;")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    private void OnEmbarkClicked()")
    mgr_body.append("    {")
    mgr_body.append("        if (!ValidateName(_characterName))")
    mgr_body.append("        {")
    mgr_body.append('            Debug.LogWarning("Invalid character name. Must be 3-20 alphanumeric characters.");')
    mgr_body.append("            return;")
    mgr_body.append("        }")
    mgr_body.append("        if (_paths.Count == 0) return;")
    mgr_body.append("        var selectedPath = _paths[_currentPathIndex];")
    mgr_body.append("        OnCharacterCreated?.Invoke(selectedPath, _appearance, _characterName);")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    private void AnimateCarouselTransition(int direction)")
    mgr_body.append("    {")
    mgr_body.append("        if (_carouselContainer == null) return;")
    mgr_body.append("        float offset = direction * 300f;")
    mgr_body.append("        var seq = Sequence.Create();")
    mgr_body.append("        seq.Chain(Tween.UIOffset(_carouselContainer, new Vector2(offset, 0), 0.15f));")
    mgr_body.append("        seq.ChainCallback(() => {")
    mgr_body.append("            UpdateDisplay();")
    mgr_body.append("            _carouselContainer.style.translate = new Translate(-offset, 0);")
    mgr_body.append("        });")
    mgr_body.append("        seq.Chain(Tween.UIOffset(_carouselContainer, Vector2.zero, 0.15f));")
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    private void UpdateDisplay()")
    mgr_body.append("    {")
    mgr_body.append("        if (_paths.Count == 0) return;")
    mgr_body.append("        var path = _paths[_currentPathIndex];")
    mgr_body.append("        if (_pathNameLabel != null) _pathNameLabel.text = path.pathName;")
    mgr_body.append("        if (_pathDescLabel != null) _pathDescLabel.text = path.description;")
    mgr_body.append("        if (_statsLabel != null)")
    mgr_body.append('            _statsLabel.text = $"STR: {path.baseStrength}  AGI: {path.baseAgility}  INT: {path.baseIntelligence}";')
    mgr_body.append("    }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Set appearance skin color index.</summary>")
    mgr_body.append("    public void SetSkinColor(int index) { _appearance.skinColorIndex = Mathf.Clamp(index, 0, _skinColors.Length - 1); }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Set appearance hair style index.</summary>")
    mgr_body.append("    public void SetHairStyle(int index) { _appearance.hairStyleIndex = Mathf.Clamp(index, 0, _hairStyles.Length - 1); }")
    mgr_body.append("")
    mgr_body.append("    /// <summary>Set appearance armor tint index.</summary>")
    mgr_body.append("    public void SetArmorTint(int index) { _appearance.armorTintIndex = Mathf.Clamp(index, 0, _armorTints.Length - 1); }")
    mgr_body.append("}")

    mgr_lines: list[str] = []
    if namespace:
        mgr_lines.extend(_wrap_namespace(mgr_body, namespace))
    else:
        mgr_lines.extend(mgr_body)
    manager_cs = "\n".join(mgr_lines)

    # --- UXML ---
    uxml_lines: list[str] = []
    uxml_lines.append('<ui:UXML xmlns:ui="UnityEngine.UIElements" xmlns:uie="UnityEditor.UIElements">')
    uxml_lines.append('    <ui:VisualElement name="character-select-root" class="character-select-root">')
    uxml_lines.append('        <ui:Label text="Choose Your Path" class="screen-title" />')
    uxml_lines.append('        <ui:VisualElement name="carousel-section" class="carousel-section">')
    uxml_lines.append('            <ui:Button name="prev-button" class="nav-button" text="&lt;" />')
    uxml_lines.append('            <ui:VisualElement name="carousel-container" class="carousel-container">')
    uxml_lines.append('                <ui:Label name="path-name" class="path-name" text="IRON" />')
    uxml_lines.append('                <ui:Label name="path-description" class="path-desc" text="Description" />')
    uxml_lines.append('                <ui:Label name="path-stats" class="path-stats" text="STR: 10  AGI: 10  INT: 10" />')
    uxml_lines.append("            </ui:VisualElement>")
    uxml_lines.append('            <ui:Button name="next-button" class="nav-button" text="&gt;" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="appearance-panel" class="appearance-panel">')
    uxml_lines.append('            <ui:Label text="Appearance" class="section-title" />')
    uxml_lines.append('            <ui:DropdownField name="skin-color" label="Skin Color" />')
    uxml_lines.append('            <ui:DropdownField name="hair-style" label="Hair Style" />')
    uxml_lines.append('            <ui:DropdownField name="armor-tint" label="Armor Tint" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:VisualElement name="name-section" class="name-section">')
    uxml_lines.append('            <ui:TextField name="name-input" label="Character Name" max-length="20" />')
    uxml_lines.append("        </ui:VisualElement>")
    uxml_lines.append('        <ui:Button name="embark-button" class="embark-button" text="Embark" />')
    uxml_lines.append("    </ui:VisualElement>")
    uxml_lines.append("</ui:UXML>")
    uxml = "\n".join(uxml_lines)

    # --- USS ---
    uss_lines: list[str] = []
    uss_lines.append("/* VeilBreakers Character Select - Dark Fantasy Theme */")
    uss_lines.append(".character-select-root {")
    uss_lines.append("    flex-grow: 1;")
    uss_lines.append("    background-color: rgb(15, 10, 8);")
    uss_lines.append("    align-items: center;")
    uss_lines.append("    justify-content: center;")
    uss_lines.append("    padding: 40px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".screen-title {")
    uss_lines.append("    -unity-font-definition: url('project://Fonts/Cinzel-Bold.ttf');")
    uss_lines.append("    font-size: 36px;")
    uss_lines.append("    color: rgb(212, 175, 55);")
    uss_lines.append("    margin-bottom: 30px;")
    uss_lines.append("    -unity-text-align: middle-center;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".carousel-section {")
    uss_lines.append("    flex-direction: row;")
    uss_lines.append("    align-items: center;")
    uss_lines.append("    margin-bottom: 20px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".carousel-container {")
    uss_lines.append("    width: 400px;")
    uss_lines.append("    padding: 24px;")
    uss_lines.append("    background-color: rgba(30, 22, 15, 0.9);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    border-color: rgb(140, 110, 60);")
    uss_lines.append("    border-radius: 8px;")
    uss_lines.append("    align-items: center;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".path-name {")
    uss_lines.append("    -unity-font-definition: url('project://Fonts/Cinzel-Bold.ttf');")
    uss_lines.append("    font-size: 28px;")
    uss_lines.append("    color: rgb(212, 175, 55);")
    uss_lines.append("    margin-bottom: 10px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".path-desc {")
    uss_lines.append("    -unity-font-definition: url('project://Fonts/Cinzel-Regular.ttf');")
    uss_lines.append("    font-size: 14px;")
    uss_lines.append("    color: rgb(180, 170, 150);")
    uss_lines.append("    white-space: normal;")
    uss_lines.append("    margin-bottom: 12px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".path-stats {")
    uss_lines.append("    font-size: 13px;")
    uss_lines.append("    color: rgb(160, 150, 130);")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".nav-button {")
    uss_lines.append("    width: 50px;")
    uss_lines.append("    height: 50px;")
    uss_lines.append("    font-size: 24px;")
    uss_lines.append("    background-color: rgba(40, 30, 20, 0.8);")
    uss_lines.append("    border-color: rgb(140, 110, 60);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    border-radius: 25px;")
    uss_lines.append("    color: rgb(212, 175, 55);")
    uss_lines.append("    margin: 0 15px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".appearance-panel {")
    uss_lines.append("    width: 350px;")
    uss_lines.append("    padding: 16px;")
    uss_lines.append("    background-color: rgba(25, 18, 12, 0.85);")
    uss_lines.append("    border-width: 1px;")
    uss_lines.append("    border-color: rgb(100, 80, 45);")
    uss_lines.append("    border-radius: 6px;")
    uss_lines.append("    margin-bottom: 20px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".section-title {")
    uss_lines.append("    -unity-font-definition: url('project://Fonts/Cinzel-Regular.ttf');")
    uss_lines.append("    font-size: 18px;")
    uss_lines.append("    color: rgb(200, 180, 140);")
    uss_lines.append("    margin-bottom: 10px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".name-section {")
    uss_lines.append("    margin-bottom: 20px;")
    uss_lines.append("}")
    uss_lines.append("")
    uss_lines.append(".embark-button {")
    uss_lines.append("    width: 200px;")
    uss_lines.append("    height: 50px;")
    uss_lines.append("    -unity-font-definition: url('project://Fonts/Cinzel-Bold.ttf');")
    uss_lines.append("    font-size: 22px;")
    uss_lines.append("    background-color: rgb(140, 110, 30);")
    uss_lines.append("    border-color: rgb(212, 175, 55);")
    uss_lines.append("    border-width: 2px;")
    uss_lines.append("    border-radius: 6px;")
    uss_lines.append("    color: rgb(255, 245, 220);")
    uss_lines.append("}")
    uss = "\n".join(uss_lines)

    return (data_so_cs, manager_cs, uxml, uss)


# ---------------------------------------------------------------------------
# RPG-08: World Map
# ---------------------------------------------------------------------------


def generate_world_map_script(
    name: str = "WorldMap",
    map_resolution: int = 512,
    fog_resolution: int = 256,
    namespace: str = "",
) -> tuple[str, str]:
    """Generate world map system with heightmap-to-texture and fog-of-war.

    Returns a tuple of (editor_cs, runtime_cs).

    The editor script generates a 2D PNG map texture from TerrainData.GetHeights()
    with color mapping (water/green/brown/snow).  The runtime MonoBehaviour
    displays the map with fog-of-war mask, player position blip, location
    markers, and zoom/pan controls.

    Args:
        name: Base name for the world map system.
        map_resolution: Resolution of the generated map texture (square).
        fog_resolution: Resolution of the fog-of-war mask (square).
        namespace: Optional C# namespace.
    """
    safe_name = sanitize_cs_identifier(name)

    # --- Editor Script: Generate map from TerrainData ---
    editor_body: list[str] = []
    editor_body.append("using UnityEditor;")
    editor_body.append("using UnityEngine;")
    editor_body.append("")
    editor_body.append("/// <summary>")
    editor_body.append("/// Editor tool to generate a 2D world map texture from TerrainData heightmap.")
    editor_body.append("/// Generated by VeilBreakers MCP toolkit.")
    editor_body.append("/// </summary>")
    editor_body.append("public static class " + safe_name + "Generator")
    editor_body.append("{")
    editor_body.append('    [MenuItem("VeilBreakers/World/Generate World Map")]')
    editor_body.append("    public static void GenerateMap()")
    editor_body.append("    {")
    editor_body.append("        var terrain = Terrain.activeTerrain;")
    editor_body.append("        if (terrain == null)")
    editor_body.append("        {")
    editor_body.append('            EditorUtility.DisplayDialog("World Map", "No active terrain found.", "OK");')
    editor_body.append("            return;")
    editor_body.append("        }")
    editor_body.append("")
    editor_body.append("        var terrainData = terrain.terrainData;")
    editor_body.append("        int resolution = " + str(map_resolution) + ";")
    editor_body.append("        var mapTexture = new Texture2D(resolution, resolution, TextureFormat.RGBA32, false);")
    editor_body.append("")
    editor_body.append("        int heightmapRes = terrainData.heightmapResolution;")
    editor_body.append("        float[,] heights = terrainData.GetHeights(0, 0, heightmapRes, heightmapRes);")
    editor_body.append("        float waterLevel = 0.15f;")
    editor_body.append("")
    editor_body.append("        for (int y = 0; y < resolution; y++)")
    editor_body.append("        {")
    editor_body.append("            for (int x = 0; x < resolution; x++)")
    editor_body.append("            {")
    editor_body.append("                int hx = (int)((float)x / resolution * (heightmapRes - 1));")
    editor_body.append("                int hy = (int)((float)y / resolution * (heightmapRes - 1));")
    editor_body.append("                float h = heights[hy, hx];")
    editor_body.append("")
    editor_body.append("                Color color;")
    editor_body.append("                if (h < waterLevel)")
    editor_body.append("                {")
    editor_body.append("                    // Water: blue")
    editor_body.append("                    color = Color.Lerp(new Color(0.1f, 0.2f, 0.5f), new Color(0.2f, 0.4f, 0.7f), h / waterLevel);")
    editor_body.append("                }")
    editor_body.append("                else if (h < 0.4f)")
    editor_body.append("                {")
    editor_body.append("                    // Low lands: dark green")
    editor_body.append("                    color = Color.Lerp(new Color(0.15f, 0.35f, 0.1f), new Color(0.3f, 0.5f, 0.2f), (h - waterLevel) / 0.25f);")
    editor_body.append("                }")
    editor_body.append("                else if (h < 0.7f)")
    editor_body.append("                {")
    editor_body.append("                    // Mid: brown")
    editor_body.append("                    color = Color.Lerp(new Color(0.4f, 0.3f, 0.15f), new Color(0.5f, 0.4f, 0.25f), (h - 0.4f) / 0.3f);")
    editor_body.append("                }")
    editor_body.append("                else")
    editor_body.append("                {")
    editor_body.append("                    // High: gray to white (snow)")
    editor_body.append("                    color = Color.Lerp(new Color(0.6f, 0.6f, 0.6f), Color.white, (h - 0.7f) / 0.3f);")
    editor_body.append("                }")
    editor_body.append("")
    editor_body.append("                mapTexture.SetPixel(x, y, color);")
    editor_body.append("            }")
    editor_body.append("        }")
    editor_body.append("")
    editor_body.append("        mapTexture.Apply();")
    editor_body.append("        byte[] pngData = mapTexture.EncodeToPNG();")
    editor_body.append('        string path = "Assets/Textures/WorldMap.png";')
    editor_body.append('        string dir = System.IO.Path.GetDirectoryName(path);')
    editor_body.append("        if (!System.IO.Directory.Exists(dir)) System.IO.Directory.CreateDirectory(dir);")
    editor_body.append("        System.IO.File.WriteAllBytes(path, pngData);")
    editor_body.append("        AssetDatabase.Refresh();")
    editor_body.append('        Debug.Log($"World map generated at {path} ({resolution}x{resolution})");')
    editor_body.append("    }")
    editor_body.append("}")

    editor_lines: list[str] = []
    if namespace:
        editor_lines.extend(_wrap_namespace(editor_body, namespace))
    else:
        editor_lines.extend(editor_body)
    editor_cs = "\n".join(editor_lines)

    # --- Runtime: World Map Display with Fog-of-War ---
    runtime_body: list[str] = []
    runtime_body.append("using System;")
    runtime_body.append("using System.Collections.Generic;")
    runtime_body.append("using UnityEngine;")
    runtime_body.append("using UnityEngine.UI;")
    runtime_body.append("using PrimeTween;")
    runtime_body.append("")
    runtime_body.append("/// <summary>")
    runtime_body.append("/// Runtime world map with fog-of-war, player position tracking, and location markers.")
    runtime_body.append("/// Generated by VeilBreakers MCP toolkit.")
    runtime_body.append("/// </summary>")
    runtime_body.append("[Serializable]")
    runtime_body.append("public class MapLocation")
    runtime_body.append("{")
    runtime_body.append("    public Vector3 worldPosition;")
    runtime_body.append("    public Sprite icon;")
    runtime_body.append("    public string label;")
    runtime_body.append("}")
    runtime_body.append("")
    runtime_body.append("public class " + safe_name + "Display : MonoBehaviour")
    runtime_body.append("{")
    runtime_body.append('    [Header("Map Setup")]')
    runtime_body.append("    [SerializeField] private RawImage _mapImage;")
    runtime_body.append("    [SerializeField] private Texture2D _mapTexture;")
    runtime_body.append("    [SerializeField] private RawImage _fogImage;")
    runtime_body.append("")
    runtime_body.append('    [Header("Fog of War")]')
    runtime_body.append("    [SerializeField] private float _revealRadius = 30f;")
    runtime_body.append("    private Texture2D _fogMask;")
    runtime_body.append("    private int _fogResolution = " + str(fog_resolution) + ";")
    runtime_body.append("    private Color[] _fogPixels;")
    runtime_body.append("")
    runtime_body.append('    [Header("Player Tracking")]')
    runtime_body.append("    [SerializeField] private Transform _playerTransform;")
    runtime_body.append("    [SerializeField] private RectTransform _playerBlip;")
    runtime_body.append("")
    runtime_body.append('    [Header("Terrain Reference")]')
    runtime_body.append("    [SerializeField] private Terrain _terrain;")
    runtime_body.append("")
    runtime_body.append('    [Header("Locations")]')
    runtime_body.append("    [SerializeField] private List<MapLocation> _locations = new List<MapLocation>();")
    runtime_body.append("")
    runtime_body.append('    [Header("Zoom & Pan")]')
    runtime_body.append("    [SerializeField] private float _zoomMin = 0.5f;")
    runtime_body.append("    [SerializeField] private float _zoomMax = 3.0f;")
    runtime_body.append("    private float _currentZoom = 1.0f;")
    runtime_body.append("    private Vector2 _panOffset = Vector2.zero;")
    runtime_body.append("")
    runtime_body.append("    private void Start()")
    runtime_body.append("    {")
    runtime_body.append("        InitializeFogMask();")
    runtime_body.append("        if (_mapImage != null && _mapTexture != null)")
    runtime_body.append("            _mapImage.texture = _mapTexture;")
    runtime_body.append("    }")
    runtime_body.append("")
    runtime_body.append("    private void Update()")
    runtime_body.append("    {")
    runtime_body.append("        if (_playerTransform != null && _terrain != null)")
    runtime_body.append("        {")
    runtime_body.append("            UpdatePlayerBlip();")
    runtime_body.append("            RevealFog();")
    runtime_body.append("        }")
    runtime_body.append("    }")
    runtime_body.append("")
    runtime_body.append("    private void InitializeFogMask()")
    runtime_body.append("    {")
    runtime_body.append("        _fogMask = new Texture2D(_fogResolution, _fogResolution, TextureFormat.RGBA32, false);")
    runtime_body.append("        _fogPixels = new Color[_fogResolution * _fogResolution];")
    runtime_body.append("        // Initialize all black (fully fogged)")
    runtime_body.append("        for (int i = 0; i < _fogPixels.Length; i++)")
    runtime_body.append("            _fogPixels[i] = Color.black;")
    runtime_body.append("        _fogMask.SetPixels(_fogPixels);")
    runtime_body.append("        _fogMask.Apply();")
    runtime_body.append("        if (_fogImage != null)")
    runtime_body.append("            _fogImage.texture = _fogMask;")
    runtime_body.append("    }")
    runtime_body.append("")
    runtime_body.append("    /// <summary>Convert world position to map UV coordinates.</summary>")
    runtime_body.append("    public Vector2 WorldToMapUV(Vector3 worldPos)")
    runtime_body.append("    {")
    runtime_body.append("        if (_terrain == null) return Vector2.zero;")
    runtime_body.append("        var terrainPos = _terrain.transform.position;")
    runtime_body.append("        var terrainSize = _terrain.terrainData.size;")
    runtime_body.append("        float u = (worldPos.x - terrainPos.x) / terrainSize.x;")
    runtime_body.append("        float v = (worldPos.z - terrainPos.z) / terrainSize.z;")
    runtime_body.append("        return new Vector2(Mathf.Clamp01(u), Mathf.Clamp01(v));")
    runtime_body.append("    }")
    runtime_body.append("")
    runtime_body.append("    private void UpdatePlayerBlip()")
    runtime_body.append("    {")
    runtime_body.append("        if (_mapImage == null) return;")
    runtime_body.append("        if (_playerBlip == null) return;")
    runtime_body.append("        Vector2 uv = WorldToMapUV(_playerTransform.position);")
    runtime_body.append("        var mapRect = _mapImage.rectTransform;")
    runtime_body.append("        _playerBlip.anchoredPosition = new Vector2(")
    runtime_body.append("            (uv.x - 0.5f) * mapRect.rect.width * _currentZoom + _panOffset.x,")
    runtime_body.append("            (uv.y - 0.5f) * mapRect.rect.height * _currentZoom + _panOffset.y")
    runtime_body.append("        );")
    runtime_body.append("    }")
    runtime_body.append("")
    runtime_body.append("    private void RevealFog()")
    runtime_body.append("    {")
    runtime_body.append("        Vector2 uv = WorldToMapUV(_playerTransform.position);")
    runtime_body.append("        int cx = (int)(uv.x * _fogResolution);")
    runtime_body.append("        int cy = (int)(uv.y * _fogResolution);")
    runtime_body.append("        float radiusPixels = _revealRadius / (_terrain.terrainData.size.x) * _fogResolution;")
    runtime_body.append("        int r = Mathf.CeilToInt(radiusPixels);")
    runtime_body.append("        bool changed = false;")
    runtime_body.append("")
    runtime_body.append("        for (int dy = -r; dy <= r; dy++)")
    runtime_body.append("        {")
    runtime_body.append("            for (int dx = -r; dx <= r; dx++)")
    runtime_body.append("            {")
    runtime_body.append("                int px = cx + dx;")
    runtime_body.append("                int py = cy + dy;")
    runtime_body.append("                if (px < 0 || px >= _fogResolution || py < 0 || py >= _fogResolution) continue;")
    runtime_body.append("                float dist = Mathf.Sqrt(dx * dx + dy * dy);")
    runtime_body.append("                if (dist > radiusPixels) continue;")
    runtime_body.append("")
    runtime_body.append("                int idx = py * _fogResolution + px;")
    runtime_body.append("                float alpha = 1.0f - Mathf.Clamp01(dist / radiusPixels);")
    runtime_body.append("                if (_fogPixels[idx].r < alpha)")
    runtime_body.append("                {")
    runtime_body.append("                    _fogPixels[idx] = new Color(alpha, alpha, alpha, 1f);")
    runtime_body.append("                    changed = true;")
    runtime_body.append("                }")
    runtime_body.append("            }")
    runtime_body.append("        }")
    runtime_body.append("")
    runtime_body.append("        if (changed)")
    runtime_body.append("        {")
    runtime_body.append("            _fogMask.SetPixels(_fogPixels);")
    runtime_body.append("            _fogMask.Apply();")
    runtime_body.append("            // Smooth fog reveal via PrimeTween")
    runtime_body.append("            if (_fogImage != null)")
    runtime_body.append("                Tween.Alpha(_fogImage, _fogImage.color.a, 1f, 0.3f);")
    runtime_body.append("        }")
    runtime_body.append("    }")
    runtime_body.append("")
    runtime_body.append("    /// <summary>Zoom the map in or out.</summary>")
    runtime_body.append("    public void SetZoom(float zoom)")
    runtime_body.append("    {")
    runtime_body.append("        _currentZoom = Mathf.Clamp(zoom, _zoomMin, _zoomMax);")
    runtime_body.append("        if (_mapImage != null)")
    runtime_body.append("            _mapImage.rectTransform.localScale = Vector3.one * _currentZoom;")
    runtime_body.append("    }")
    runtime_body.append("")
    runtime_body.append("    /// <summary>Pan the map by an offset.</summary>")
    runtime_body.append("    public void Pan(Vector2 delta)")
    runtime_body.append("    {")
    runtime_body.append("        _panOffset += delta;")
    runtime_body.append("    }")
    runtime_body.append("")
    runtime_body.append("    /// <summary>Add a location marker to the map.</summary>")
    runtime_body.append("    public void AddLocation(Vector3 worldPos, Sprite icon, string label)")
    runtime_body.append("    {")
    runtime_body.append("        _locations.Add(new MapLocation { worldPosition = worldPos, icon = icon, label = label });")
    runtime_body.append("    }")
    runtime_body.append("}")

    runtime_lines: list[str] = []
    if namespace:
        runtime_lines.extend(_wrap_namespace(runtime_body, namespace))
    else:
        runtime_lines.extend(runtime_body)
    runtime_cs = "\n".join(runtime_lines)

    return (editor_cs, runtime_cs)


# ---------------------------------------------------------------------------
# EQUIP-07: Rarity VFX
# ---------------------------------------------------------------------------


def generate_rarity_vfx_script(
    name: str = "RarityVFX",
    namespace: str = "",
) -> str:
    """Generate rarity VFX MonoBehaviour with 5 tiers.

    Returns a single MonoBehaviour C# string configuring ParticleSystem
    emission rate and material emission glow per rarity tier (Common gray
    through Legendary gold with sparkle effect).

    Args:
        name: Base name for the rarity VFX controller.
        namespace: Optional C# namespace.
    """
    safe_name = sanitize_cs_identifier(name)

    body: list[str] = []
    body.append("using UnityEngine;")
    body.append("")
    body.append("/// <summary>")
    body.append("/// Equipment rarity visual effects with 5 tiers: Common through Legendary.")
    body.append("/// Configures ParticleSystem emission and material emission glow per tier.")
    body.append("/// Generated by VeilBreakers MCP toolkit.")
    body.append("/// </summary>")
    body.append("public enum ItemRarity")
    body.append("{")
    body.append("    Common = 0,")
    body.append("    Uncommon = 1,")
    body.append("    Rare = 2,")
    body.append("    Epic = 3,")
    body.append("    Legendary = 4")
    body.append("}")
    body.append("")
    body.append("public class " + safe_name + "Controller : MonoBehaviour")
    body.append("{")
    body.append('    [Header("VFX Components")]')
    body.append("    [SerializeField] private ParticleSystem _particleSystem;")
    body.append("    [SerializeField] private ParticleSystem _legendarySparkleSystem;")
    body.append("    [SerializeField] private Renderer _renderer;")
    body.append("")
    body.append('    [Header("Current Rarity")]')
    body.append("    [SerializeField] private ItemRarity _currentRarity = ItemRarity.Common;")
    body.append("")
    body.append("    private MaterialPropertyBlock _propBlock;")
    body.append("")
    body.append("    // Rarity tier configurations: color (RGBA), glow intensity, particle rate")
    body.append("    private static readonly Color[] RarityColors = new Color[]")
    body.append("    {")
    body.append("        new Color(0.5f, 0.5f, 0.5f, 1.0f),   // Common: gray")
    body.append("        new Color(0.2f, 0.8f, 0.2f, 1.0f),   // Uncommon: green")
    body.append("        new Color(0.2f, 0.4f, 1.0f, 1.0f),   // Rare: blue")
    body.append("        new Color(0.6f, 0.2f, 0.9f, 1.0f),   // Epic: purple")
    body.append("        new Color(1.0f, 0.8f, 0.1f, 1.0f),   // Legendary: gold")
    body.append("    };")
    body.append("")
    body.append("    private static readonly float[] GlowIntensities = new float[]")
    body.append("    {")
    body.append("        0.0f,   // Common")
    body.append("        0.3f,   // Uncommon")
    body.append("        0.6f,   // Rare")
    body.append("        0.8f,   // Epic")
    body.append("        1.2f,   // Legendary")
    body.append("    };")
    body.append("")
    body.append("    private static readonly int[] ParticleRates = new int[]")
    body.append("    {")
    body.append("        0,    // Common")
    body.append("        5,    // Uncommon")
    body.append("        15,   // Rare")
    body.append("        30,   // Epic")
    body.append("        60,   // Legendary")
    body.append("    };")
    body.append("")
    body.append("    private void Awake()")
    body.append("    {")
    body.append("        _propBlock = new MaterialPropertyBlock();")
    body.append("        SetRarity((int)_currentRarity);")
    body.append("    }")
    body.append("")
    body.append("    /// <summary>Set the rarity tier (0=Common through 4=Legendary).</summary>")
    body.append("    public void SetRarity(int rarityTier)")
    body.append("    {")
    body.append("        rarityTier = Mathf.Clamp(rarityTier, 0, 4);")
    body.append("        _currentRarity = (ItemRarity)rarityTier;")
    body.append("")
    body.append("        // Configure particle emission rate")
    body.append("        if (_particleSystem != null)")
    body.append("        {")
    body.append("            var emission = _particleSystem.emission;")
    body.append("            emission.rateOverTime = ParticleRates[rarityTier];")
    body.append("            var main = _particleSystem.main;")
    body.append("            main.startColor = RarityColors[rarityTier];")
    body.append("")
    body.append("            if (ParticleRates[rarityTier] > 0 && !_particleSystem.isPlaying)")
    body.append("                _particleSystem.Play();")
    body.append("            else if (ParticleRates[rarityTier] == 0 && _particleSystem.isPlaying)")
    body.append("                _particleSystem.Stop();")
    body.append("        }")
    body.append("")
    body.append("        // Set material emission via MaterialPropertyBlock")
    body.append("        if (_renderer != null)")
    body.append("        {")
    body.append("            _renderer.GetPropertyBlock(_propBlock);")
    body.append("            Color emissionColor = RarityColors[rarityTier] * GlowIntensities[rarityTier];")
    body.append('            _propBlock.SetColor("_EmissionColor", emissionColor);')
    body.append("            _renderer.SetPropertyBlock(_propBlock);")
    body.append("        }")
    body.append("")
    body.append("        // Legendary tier: activate gold sparkle particle system")
    body.append("        if (_legendarySparkleSystem != null)")
    body.append("        {")
    body.append("            if (_currentRarity == ItemRarity.Legendary)")
    body.append("            {")
    body.append("                var sparkleMain = _legendarySparkleSystem.main;")
    body.append("                sparkleMain.startColor = new Color(1.0f, 0.9f, 0.4f, 1.0f);")
    body.append("                var sparkleEmission = _legendarySparkleSystem.emission;")
    body.append("                sparkleEmission.rateOverTime = 30;")
    body.append("                if (!_legendarySparkleSystem.isPlaying)")
    body.append("                    _legendarySparkleSystem.Play();")
    body.append("            }")
    body.append("            else")
    body.append("            {")
    body.append("                _legendarySparkleSystem.Stop();")
    body.append("            }")
    body.append("        }")
    body.append("    }")
    body.append("}")

    lines: list[str] = []
    if namespace:
        lines.extend(_wrap_namespace(body, namespace))
    else:
        lines.extend(body)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# EQUIP-08: Corruption VFX
# ---------------------------------------------------------------------------


def generate_corruption_vfx_script(
    name: str = "CorruptionVFX",
    namespace: str = "",
) -> str:
    """Generate corruption VFX MonoBehaviour with 0-100% progressive visual.

    Returns a single MonoBehaviour C# string that drives material properties
    (_CorruptionAmount, _VeinIntensity), color shift, emission, particle
    emission rate, and a PrimeTween pulse at 100% corruption.

    Args:
        name: Base name for the corruption VFX controller.
        namespace: Optional C# namespace.
    """
    safe_name = sanitize_cs_identifier(name)

    body: list[str] = []
    body.append("using UnityEngine;")
    body.append("using PrimeTween;")
    body.append("")
    body.append("/// <summary>")
    body.append("/// Equipment corruption visual progression (0-100%).")
    body.append("/// Drives material properties for vein patterns, color shift, and emission.")
    body.append("/// Particle emission scales with corruption level.")
    body.append("/// Generated by VeilBreakers MCP toolkit.")
    body.append("/// </summary>")
    body.append("public class " + safe_name + "Controller : MonoBehaviour")
    body.append("{")
    body.append('    [Header("Visual Components")]')
    body.append("    [SerializeField] private Renderer _renderer;")
    body.append("    [SerializeField] private ParticleSystem _corruptionParticles;")
    body.append("")
    body.append('    [Header("Settings")]')
    body.append("    [SerializeField, Range(0f, 1f)] private float _corruptionAmount;")
    body.append("    [SerializeField] private float _maxParticleRate = 50f;")
    body.append("    [SerializeField] private Color _corruptionColor = new Color(0.3f, 0.1f, 0.4f, 1f);")
    body.append("")
    body.append("    private Material _material;")
    body.append("    private Color _originalColor;")
    body.append("    private Tween _pulseTween;")
    body.append("")
    body.append("    private void Awake()")
    body.append("    {")
    body.append("        if (_renderer != null)")
    body.append("        {")
    body.append("            _material = _renderer.material;")
    body.append('            _originalColor = _material.GetColor("_BaseColor");')
    body.append("        }")
    body.append("    }")
    body.append("")
    body.append("    private void OnDestroy()")
    body.append("    {")
    body.append("        if (_pulseTween.isAlive)")
    body.append("            _pulseTween.Stop();")
    body.append("    }")
    body.append("")
    body.append("    /// <summary>Set corruption amount (0.0 to 1.0). Drives all visual effects.</summary>")
    body.append("    public void SetCorruption(float amount)")
    body.append("    {")
    body.append("        _corruptionAmount = Mathf.Clamp01(amount);")
    body.append("        ApplyCorruptionVisuals();")
    body.append("    }")
    body.append("")
    body.append("    private void ApplyCorruptionVisuals()")
    body.append("    {")
    body.append("        if (_material == null) return;")
    body.append("        float corruption = _corruptionAmount;")
    body.append("")
    body.append("        // --- Material Property: _CorruptionAmount ---")
    body.append('        _material.SetFloat("_CorruptionAmount", corruption);')
    body.append("")
    body.append("        // --- Vein Pattern Intensity ---")
    body.append("        // 25%: subtle vein patterns appear")
    body.append("        float veinIntensity = 0f;")
    body.append("        if (corruption >= 0.25f)")
    body.append("            veinIntensity = corruption * 1.5f;")
    body.append('        _material.SetFloat("_VeinIntensity", veinIntensity);')
    body.append("")
    body.append("        // --- Color Shift ---")
    body.append("        // 50%: color shift becomes noticeable")
    body.append("        Color currentColor = Color.Lerp(_originalColor, _corruptionColor, corruption);")
    body.append('        _material.SetColor("_BaseColor", currentColor);')
    body.append("")
    body.append("        // --- Emission (vein glow) ---")
    body.append("        // 75%: strong vein glow")
    body.append("        Color veinColor = _corruptionColor;")
    body.append('        _material.SetColor("_EmissionColor", veinColor * corruption * 2f);')
    body.append("")
    body.append("        // --- Particle System ---")
    body.append("        if (_corruptionParticles != null)")
    body.append("        {")
    body.append("            var emission = _corruptionParticles.emission;")
    body.append("            emission.rateOverTime = _maxParticleRate * corruption;")
    body.append("")
    body.append("            // 50%: occasional particle bursts")
    body.append("            if (corruption >= 0.5f && corruption < 0.75f)")
    body.append("            {")
    body.append("                emission.SetBursts(new ParticleSystem.Burst[]")
    body.append("                {")
    body.append("                    new ParticleSystem.Burst(0f, 5, 10, 3, 2f)")
    body.append("                });")
    body.append("            }")
    body.append("            // 75%: constant particle emission")
    body.append("            else if (corruption >= 0.75f)")
    body.append("            {")
    body.append("                emission.SetBursts(new ParticleSystem.Burst[]")
    body.append("                {")
    body.append("                    new ParticleSystem.Burst(0f, 10, 20, 5, 1f)")
    body.append("                });")
    body.append("            }")
    body.append("")
    body.append("            if (corruption > 0f && !_corruptionParticles.isPlaying)")
    body.append("                _corruptionParticles.Play();")
    body.append("            else if (corruption == 0f && _corruptionParticles.isPlaying)")
    body.append("                _corruptionParticles.Stop();")
    body.append("        }")
    body.append("")
    body.append("        // --- 100%: Pulsing glow effect via PrimeTween ---")
    body.append("        if (corruption >= 1.0f)")
    body.append("        {")
    body.append("            if (!_pulseTween.isAlive)")
    body.append("            {")
    body.append("                _pulseTween = Tween.Custom(0f, 1f, 1.0f, ease: Ease.InOutSine, cycles: -1, cycleMode: CycleMode.Yoyo, onValueChange: val =>")
    body.append("                {")
    body.append("                    if (_material != null)")
    body.append("                    {")
    body.append("                        float pulseIntensity = 1.5f + val * 1.5f;")
    body.append('                        _material.SetColor("_EmissionColor", _corruptionColor * pulseIntensity);')
    body.append("                    }")
    body.append("                });")
    body.append("            }")
    body.append("        }")
    body.append("        else")
    body.append("        {")
    body.append("            if (_pulseTween.isAlive)")
    body.append("                _pulseTween.Stop();")
    body.append("        }")
    body.append("    }")
    body.append("}")

    lines: list[str] = []
    if namespace:
        lines.extend(_wrap_namespace(body, namespace))
    else:
        lines.extend(body)

    return "\n".join(lines)
