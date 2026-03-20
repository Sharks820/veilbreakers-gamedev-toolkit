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
    "VENOM": ("0.2f", "0.8f", "0.2f", "1f"),
    "SURGE": ("0.2f", "0.4f", "1f", "1f"),
    "DREAD": ("0.6f", "0.1f", "0.9f", "1f"),
    "BLAZE": ("1f", "0.5f", "0f", "1f"),
    "FROST": ("0f", "0.9f", "0.9f", "1f"),
    "VOID": ("0.3f", "0f", "0.5f", "1f"),
    "HOLY": ("1f", "0.85f", "0f", "1f"),
    "NATURE": ("0.13f", "0.55f", "0.13f", "1f"),
    "SHADOW": ("0.3f", "0.3f", "0.3f", "1f"),
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
    safe_name = _sanitize_cs_identifier(name)
    safe_target = _sanitize_cs_string(follow_target)
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
    layer_str = " | ".join([f'LayerMask.GetMask("{_sanitize_cs_string(layer)}")' for layer in layers])
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
        r_body.append(f"        {_sanitize_cs_identifier(m)},")
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
    layer_mask_str = " | ".join([f'LayerMask.GetMask("{_sanitize_cs_string(layer)}")' for layer in layers])
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
    safe_name = _sanitize_cs_identifier(name)

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
    safe_name = _sanitize_cs_identifier(name)
    safe_prompt = _sanitize_cs_string(prompt_text)

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
    safe_name = _sanitize_cs_identifier(name)
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
    safe_font_path = _sanitize_cs_string(font_path)
    safe_output_path = _sanitize_cs_string(output_path)

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
    char_set = _sanitize_cs_string(character_set) if character_set else default_chars

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
    safe_name = _sanitize_cs_identifier(name)
    safe_font_path = _sanitize_cs_string(font_asset_path) if font_asset_path else ""
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
