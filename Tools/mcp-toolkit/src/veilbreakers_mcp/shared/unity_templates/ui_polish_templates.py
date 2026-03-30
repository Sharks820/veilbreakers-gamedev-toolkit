"""AAA Dark Fantasy UI/UX Polish C# template generators for Unity.

Implements ornate dark fantasy UI systems: procedural frames with rune
decorations, 3D icon render pipeline, context-sensitive cursors, rich
tooltips with equipment comparison, radial ability wheel, notification
toasts, loading screens, and material-based UI shaders.

All UI uses Unity UI Toolkit (UXML + USS), PrimeTween for animation
(NOT DOTween), and follows VeilBreakers dark fantasy art direction.

Each function returns a dict with ``script_path``, ``script_content``,
and ``next_steps``.  C# source is built via line-based string
concatenation following the established VeilBreakers template convention.

Phase 22 -- AAA Dark Fantasy UI/UX Polish
Requirements: UIPOL-01 through UIPOL-08
"""

from __future__ import annotations

from typing import Any

from ._cs_sanitize import sanitize_cs_identifier


# VeilBreakers dark fantasy color palette (hex)
VB_COLORS = {
    "deep_black": "#1a1a2e",
    "rich_gold": "#c9a84c",
    "crimson_red": "#8b0000",
    "weathered_bronze": "#4a3728",
    "dark_purple": "#2d1b2e",
    "parchment": "#d4c5a9",
    "steel_grey": "#6b6b7b",
    "void_blue": "#1a0a3e",
    "corruption_pulse": "#3d0f0f",
}

# Rarity color mapping
RARITY_COLORS = {
    "Common": "#808080",
    "Uncommon": "#2ecc71",
    "Rare": "#3498db",
    "Epic": "#9b59b6",
    "Legendary": "#f1c40f",
    "Corrupted": "#e74c3c",
}


# ---------------------------------------------------------------------------
# UIPOL-01: Procedural UI Frames
# ---------------------------------------------------------------------------


def generate_procedural_frame_script(
    frame_name: str = "DarkFantasyFrame",
    style: str = "gothic",
    border_width: int = 4,
    corner_style: str = "ornate",
    inner_glow: bool = True,
    rune_brand: str = "IRON",
) -> dict[str, Any]:
    """Generate C# + USS for dark fantasy UI frames with ornate borders.

    Creates procedural UI frames with configurable dark fantasy styling:
    gothic/runic/corrupted/noble themes, ornate corner decorations,
    weathered metallic edges, rune overlays, and inner glow effects.

    Args:
        frame_name: Name for the generated frame class.
        style: Frame style -- gothic, runic, corrupted, noble.
        border_width: Border thickness in pixels.
        corner_style: Corner decoration -- ornate, simple, rune, skull.
        inner_glow: Whether to add inner glow effect.
        rune_brand: Combat brand for rune decorations (IRON, SAVAGE, etc).

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    safe_name = sanitize_cs_identifier(frame_name)
    class_name = f"VB_{safe_name}"

    valid_styles = {"gothic", "runic", "corrupted", "noble"}
    if style not in valid_styles:
        style = "gothic"

    valid_corners = {"ornate", "simple", "rune", "skull"}
    if corner_style not in valid_corners:
        corner_style = "ornate"

    valid_brands = [
        "IRON", "SAVAGE", "SURGE", "VENOM", "DREAD",
        "LEECH", "GRACE", "MEND", "RUIN", "VOID",
    ]
    if rune_brand not in valid_brands:
        rune_brand = "IRON"

    # Style-specific USS classes
    style_colors = {
        "gothic": (VB_COLORS["deep_black"], VB_COLORS["rich_gold"], VB_COLORS["steel_grey"]),
        "runic": (VB_COLORS["void_blue"], VB_COLORS["rich_gold"], VB_COLORS["parchment"]),
        "corrupted": (VB_COLORS["corruption_pulse"], VB_COLORS["crimson_red"], VB_COLORS["dark_purple"]),
        "noble": (VB_COLORS["dark_purple"], VB_COLORS["rich_gold"], VB_COLORS["parchment"]),
    }
    bg_color, accent_color, text_color = style_colors[style]

    inner_glow_uss = ""
    if inner_glow:
        inner_glow_uss = f"""
.vb-frame__inner-glow {{
    position: absolute;
    left: 0;
    top: 0;
    right: 0;
    bottom: 0;
    border-width: 2px;
    border-color: {accent_color}40;
    border-radius: 2px;
}}"""

    uss_content = f"""/* VeilBreakers Dark Fantasy Frame - {style.title()} Style */
/* Auto-generated USS for {class_name} */

.vb-frame {{
    background-color: {bg_color};
    border-width: {border_width}px;
    border-color: {accent_color};
    border-radius: 4px;
    padding: 12px;
    margin: 4px;
}}

.vb-frame--{style} {{
    background-color: {bg_color};
    border-color: {accent_color};
}}

.vb-frame__border-outer {{
    position: absolute;
    left: -2px;
    top: -2px;
    right: -2px;
    bottom: -2px;
    border-width: 1px;
    border-color: {accent_color}80;
    border-radius: 6px;
}}

.vb-frame__border-inner {{
    position: absolute;
    left: 2px;
    top: 2px;
    right: 2px;
    bottom: 2px;
    border-width: 1px;
    border-color: {accent_color}40;
    border-radius: 2px;
}}

.vb-frame__corner {{
    position: absolute;
    width: 24px;
    height: 24px;
    background-color: {accent_color};
    border-radius: 2px;
}}

.vb-frame__corner--tl {{
    left: -4px;
    top: -4px;
}}

.vb-frame__corner--tr {{
    right: -4px;
    top: -4px;
}}

.vb-frame__corner--bl {{
    left: -4px;
    bottom: -4px;
}}

.vb-frame__corner--br {{
    right: -4px;
    bottom: -4px;
}}

.vb-frame__title-bar {{
    height: 36px;
    background-color: {accent_color}30;
    border-bottom-width: 2px;
    border-bottom-color: {accent_color};
    padding: 4px 12px;
    margin-bottom: 8px;
    -unity-text-align: middle-center;
}}

.vb-frame__title-text {{
    color: {text_color};
    font-size: 16px;
    -unity-font-style: bold;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

.vb-frame__content {{
    flex-grow: 1;
    padding: 8px;
}}

.vb-frame__rune-decoration {{
    position: absolute;
    width: 16px;
    height: 16px;
    background-color: {accent_color}60;
    border-radius: 8px;
}}

.vb-frame__edge-decoration {{
    position: absolute;
    background-color: {accent_color}20;
    border-width: 1px;
    border-color: {accent_color}40;
}}

.vb-frame__edge-decoration--top {{
    left: 30px;
    right: 30px;
    top: -1px;
    height: 3px;
}}

.vb-frame__edge-decoration--bottom {{
    left: 30px;
    right: 30px;
    bottom: -1px;
    height: 3px;
}}
{inner_glow_uss}"""

    script = f'''// VeilBreakers Auto-Generated: Procedural Dark Fantasy UI Frame
// Style: {style.title()} | Corner: {corner_style} | Brand: {rune_brand}
using UnityEngine;
using UnityEngine.UIElements;

/// <summary>
/// Procedural dark fantasy UI frame with ornate borders, corner decorations,
/// rune overlays, and configurable styling. Uses UI Toolkit (UXML/USS).
/// </summary>
public class {class_name} : MonoBehaviour
{{
    [Header("Frame Configuration")]
    [SerializeField] private UIDocument uiDocument;
    [SerializeField] private string frameTitle = "VeilBreakers";
    [SerializeField] private FrameStyle frameStyle = FrameStyle.{style.title()};
    [SerializeField] private CornerStyle cornerStyle = CornerStyle.{corner_style.title()};
    [SerializeField] private bool showRuneDecorations = true;
    [SerializeField] private bool showInnerGlow = {str(inner_glow).lower()};
    [SerializeField] private int borderWidth = {border_width};

    [Header("Animation")]
    [SerializeField] private float fadeInDuration = 0.3f;
    [SerializeField] private float glowPulseSpeed = 1.5f;
    [SerializeField] private float glowPulseIntensity = 0.3f;

    public enum FrameStyle {{ Gothic, Runic, Corrupted, Noble }}
    public enum CornerStyle {{ Ornate, Simple, Rune, Skull }}

    private VisualElement _root;
    private VisualElement _frameContainer;
    private VisualElement _titleBar;
    private Label _titleLabel;
    private VisualElement _contentArea;
    private VisualElement _innerGlow;

    // Brand-specific rune unicode symbols
    private static readonly System.Collections.Generic.Dictionary<string, string> BrandRunes =
        new System.Collections.Generic.Dictionary<string, string>
    {{
        {{ "IRON", "\\u2694" }},     // Swords
        {{ "SAVAGE", "\\u2620" }},   // Skull
        {{ "SURGE", "\\u26A1" }},    // Lightning
        {{ "VENOM", "\\u2623" }},    // Biohazard
        {{ "DREAD", "\\u2620" }},    // Skull variant
        {{ "LEECH", "\\u2764" }},    // Heart
        {{ "GRACE", "\\u2727" }},    // Star
        {{ "MEND", "\\u2695" }},     // Caduceus
        {{ "RUIN", "\\u2622" }},     // Radiation
        {{ "VOID", "\\u29BF" }},     // Circle
    }};

    private void OnEnable()
    {{
        if (uiDocument == null)
            uiDocument = GetComponent<UIDocument>();
        if (uiDocument == null) return;

        _root = uiDocument.rootVisualElement;
        BuildFrame();
    }}

    /// <summary>
    /// Build the procedural frame structure in the UI Document.
    /// </summary>
    public void BuildFrame()
    {{
        if (_root == null) return;
        _root.Clear();

        // Main frame container
        _frameContainer = new VisualElement();
        _frameContainer.AddToClassList("vb-frame");
        _frameContainer.AddToClassList($"vb-frame--{{frameStyle.ToString().ToLower()}}");
        _frameContainer.style.borderTopWidth = borderWidth;
        _frameContainer.style.borderBottomWidth = borderWidth;
        _frameContainer.style.borderLeftWidth = borderWidth;
        _frameContainer.style.borderRightWidth = borderWidth;

        // Outer border decoration
        var outerBorder = new VisualElement();
        outerBorder.AddToClassList("vb-frame__border-outer");
        _frameContainer.Add(outerBorder);

        // Inner border decoration
        var innerBorder = new VisualElement();
        innerBorder.AddToClassList("vb-frame__border-inner");
        _frameContainer.Add(innerBorder);

        // Corner decorations
        AddCornerDecorations(_frameContainer);

        // Edge decorations
        AddEdgeDecorations(_frameContainer);

        // Title bar
        _titleBar = new VisualElement();
        _titleBar.AddToClassList("vb-frame__title-bar");
        _titleLabel = new Label(frameTitle);
        _titleLabel.AddToClassList("vb-frame__title-text");
        _titleBar.Add(_titleLabel);
        _frameContainer.Add(_titleBar);

        // Content area
        _contentArea = new VisualElement();
        _contentArea.AddToClassList("vb-frame__content");
        _frameContainer.Add(_contentArea);

        // Rune decorations
        if (showRuneDecorations)
            AddRuneDecorations(_frameContainer);

        // Inner glow overlay
        if (showInnerGlow)
        {{
            _innerGlow = new VisualElement();
            _innerGlow.AddToClassList("vb-frame__inner-glow");
            _frameContainer.Add(_innerGlow);
        }}

        _root.Add(_frameContainer);

        // Fade-in animation via PrimeTween
        _frameContainer.style.opacity = 0f;
        AnimateFadeIn();
    }}

    private void AddCornerDecorations(VisualElement parent)
    {{
        string[] positions = {{ "tl", "tr", "bl", "br" }};
        foreach (var pos in positions)
        {{
            var corner = new VisualElement();
            corner.AddToClassList("vb-frame__corner");
            corner.AddToClassList($"vb-frame__corner--{{pos}}");

            // Style-specific corner sizing
            int size = cornerStyle switch
            {{
                CornerStyle.Ornate => 24,
                CornerStyle.Simple => 12,
                CornerStyle.Rune => 20,
                CornerStyle.Skull => 28,
                _ => 24
            }};
            corner.style.width = size;
            corner.style.height = size;

            parent.Add(corner);
        }}
    }}

    private void AddEdgeDecorations(VisualElement parent)
    {{
        var topEdge = new VisualElement();
        topEdge.AddToClassList("vb-frame__edge-decoration");
        topEdge.AddToClassList("vb-frame__edge-decoration--top");
        parent.Add(topEdge);

        var bottomEdge = new VisualElement();
        bottomEdge.AddToClassList("vb-frame__edge-decoration");
        bottomEdge.AddToClassList("vb-frame__edge-decoration--bottom");
        parent.Add(bottomEdge);
    }}

    private void AddRuneDecorations(VisualElement parent)
    {{
        string brand = "{rune_brand}";
        if (!BrandRunes.TryGetValue(brand, out string runeSymbol))
            runeSymbol = "\\u2694";

        // Place runes at midpoints of each edge
        float[] xPositions = {{ 0.25f, 0.5f, 0.75f }};
        foreach (float xPct in xPositions)
        {{
            var rune = new Label(runeSymbol);
            rune.AddToClassList("vb-frame__rune-decoration");
            rune.style.position = Position.Absolute;
            rune.style.left = Length.Percent(xPct * 100f);
            rune.style.top = -8;
            rune.style.fontSize = 12;
            rune.style.unityTextAlign = TextAnchor.MiddleCenter;
            parent.Add(rune);
        }}
    }}

    private void AnimateFadeIn()
    {{
        // PrimeTween fade-in: animate opacity from 0 to 1
        // Usage: Tween.UIAlpha(_frameContainer, 0f, 1f, fadeInDuration);
        // Fallback for when PrimeTween is not yet imported:
        _frameContainer.schedule.Execute(() =>
        {{
            _frameContainer.style.opacity = 1f;
        }}).StartingIn((long)(fadeInDuration * 1000));
    }}

    private void Update()
    {{
        if (showInnerGlow && _innerGlow != null)
        {{
            float pulse = (Mathf.Sin(Time.time * glowPulseSpeed) + 1f) * 0.5f;
            float alpha = glowPulseIntensity * pulse;
            _innerGlow.style.borderTopColor = new Color(0.79f, 0.66f, 0.3f, alpha);
            _innerGlow.style.borderBottomColor = new Color(0.79f, 0.66f, 0.3f, alpha);
            _innerGlow.style.borderLeftColor = new Color(0.79f, 0.66f, 0.3f, alpha);
            _innerGlow.style.borderRightColor = new Color(0.79f, 0.66f, 0.3f, alpha);
        }}
    }}

    /// <summary>
    /// Get the content area VisualElement to add child UI elements.
    /// </summary>
    public VisualElement GetContentArea() => _contentArea;

    /// <summary>
    /// Update the frame title text.
    /// </summary>
    public void SetTitle(string title)
    {{
        frameTitle = title;
        if (_titleLabel != null)
            _titleLabel.text = title;
    }}

    /// <summary>
    /// Change frame style at runtime.
    /// </summary>
    public void SetStyle(FrameStyle newStyle)
    {{
        frameStyle = newStyle;
        BuildFrame();
    }}
}}
'''

    return {
        "script_path": f"Assets/Scripts/Runtime/UI/{class_name}.cs",
        "script_content": script,
        "uss_content": uss_content,
        "uss_path": f"Assets/UI/Styles/VB_{safe_name}.uss",
        "next_steps": [
            "Save the C# script and USS file to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Create a UIDocument in your scene and attach the component",
            "Add the USS file as a stylesheet to the UIDocument",
            "Customize frame_title, style, and corner decorations in Inspector",
        ],
    }


# ---------------------------------------------------------------------------
# UIPOL-02: Icon Render Pipeline
# ---------------------------------------------------------------------------


def generate_icon_render_pipeline_script(
    icon_size: int = 256,
    render_angle: str = "front_three_quarter",
    light_setup: str = "three_point",
    rarity_border: bool = True,
    background_gradient: bool = True,
) -> dict[str, Any]:
    """Generate C# editor script for rendering 3D item icons.

    Creates a dedicated icon render scene with controlled lighting,
    renders item prefabs from a configurable angle using RenderTexture,
    and post-processes with rarity borders and background gradients.

    Args:
        icon_size: Icon resolution in pixels (square).
        render_angle: Camera angle preset -- front, side, front_three_quarter, top_down.
        light_setup: Lighting preset -- three_point, dramatic, flat, rim.
        rarity_border: Whether to add rarity-colored border to icons.
        background_gradient: Whether to add a background gradient.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    valid_angles = {"front", "side", "front_three_quarter", "top_down"}
    if render_angle not in valid_angles:
        render_angle = "front_three_quarter"

    valid_lights = {"three_point", "dramatic", "flat", "rim"}
    if light_setup not in valid_lights:
        light_setup = "three_point"

    # Camera angle presets (position, rotation euler angles)
    angle_presets = {
        "front": ("new Vector3(0f, 1f, -2f)", "new Vector3(15f, 0f, 0f)"),
        "side": ("new Vector3(-2f, 1f, 0f)", "new Vector3(15f, 90f, 0f)"),
        "front_three_quarter": ("new Vector3(-1.5f, 1.2f, -1.5f)", "new Vector3(20f, 45f, 0f)"),
        "top_down": ("new Vector3(0f, 3f, -0.5f)", "new Vector3(75f, 0f, 0f)"),
    }
    cam_pos, cam_rot = angle_presets[render_angle]

    rarity_block = ""
    if rarity_border:
        rarity_block = '''
    private static readonly Dictionary<string, Color> RarityColors = new Dictionary<string, Color>
    {
        { "Common", new Color(0.5f, 0.5f, 0.5f, 1f) },
        { "Uncommon", new Color(0.18f, 0.8f, 0.44f, 1f) },
        { "Rare", new Color(0.2f, 0.6f, 0.86f, 1f) },
        { "Epic", new Color(0.61f, 0.35f, 0.71f, 1f) },
        { "Legendary", new Color(0.95f, 0.77f, 0.06f, 1f) },
        { "Corrupted", new Color(0.91f, 0.3f, 0.24f, 1f) },
    };

    private static void ApplyRarityBorder(Texture2D texture, string rarity, int borderWidth = 4)
    {
        if (!RarityColors.TryGetValue(rarity, out Color borderColor))
            borderColor = RarityColors["Common"];

        int w = texture.width;
        int h = texture.height;
        Color[] pixels = texture.GetPixels();

        for (int x = 0; x < w; x++)
        {
            for (int y = 0; y < h; y++)
            {
                bool isBorder = x < borderWidth || x >= w - borderWidth ||
                                y < borderWidth || y >= h - borderWidth;
                if (isBorder)
                    pixels[y * w + x] = borderColor;
            }
        }

        // Corner chamfer for ornate feel
        int chamfer = borderWidth + 2;
        for (int cx = 0; cx < chamfer; cx++)
        {
            for (int cy = 0; cy < chamfer; cy++)
            {
                if (cx + cy < chamfer)
                {
                    // Set corner pixels to accent gold
                    Color gold = new Color(0.79f, 0.66f, 0.3f, 1f);
                    pixels[cy * w + cx] = gold;
                    pixels[cy * w + (w - 1 - cx)] = gold;
                    pixels[(h - 1 - cy) * w + cx] = gold;
                    pixels[(h - 1 - cy) * w + (w - 1 - cx)] = gold;
                }
            }
        }

        texture.SetPixels(pixels);
        texture.Apply();
    }'''

    gradient_block = ""
    if background_gradient:
        gradient_block = '''
    private static void ApplyBackgroundGradient(Texture2D texture)
    {
        int w = texture.width;
        int h = texture.height;
        Color[] pixels = texture.GetPixels();

        Color topColor = new Color(0.1f, 0.1f, 0.18f, 1f);
        Color bottomColor = new Color(0.05f, 0.05f, 0.08f, 1f);

        for (int y = 0; y < h; y++)
        {
            float t = (float)y / h;
            Color bgColor = Color.Lerp(bottomColor, topColor, t);

            for (int x = 0; x < w; x++)
            {
                int idx = y * w + x;
                Color pixel = pixels[idx];
                if (pixel.a < 0.01f)
                {
                    pixels[idx] = bgColor;
                }
                else if (pixel.a < 1f)
                {
                    pixels[idx] = Color.Lerp(bgColor, pixel, pixel.a);
                    pixels[idx].a = 1f;
                }
            }
        }

        texture.SetPixels(pixels);
        texture.Apply();
    }'''

    script = f'''// VeilBreakers Auto-Generated: Icon Render Pipeline
// Renders 3D item prefabs as stylized 2D icons for inventory UI
#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System.IO;
using System.Collections.Generic;

/// <summary>
/// Editor tool for rendering equipment/item prefabs as high-quality 2D icons.
/// Creates a temporary render scene with controlled lighting and camera angles.
/// Post-processes with rarity borders and background gradients.
/// </summary>
public static class VB_IconRenderPipeline
{{
    private const int DefaultIconSize = {icon_size};
    private const string OutputFolder = "Assets/Art/Icons/Generated";

    [MenuItem("VeilBreakers/UI/Render Selected Item Icon")]
    public static void RenderSelectedIcon()
    {{
        GameObject selected = Selection.activeGameObject;
        if (selected == null)
        {{
            EditorUtility.DisplayDialog("Icon Render", "Select a prefab in the Project window.", "OK");
            return;
        }}

        string path = RenderIcon(selected, "Common", DefaultIconSize);
        if (!string.IsNullOrEmpty(path))
        {{
            EditorUtility.DisplayDialog("Icon Render", $"Icon saved to: {{path}}", "OK");
            AssetDatabase.Refresh();
        }}
    }}

    [MenuItem("VeilBreakers/UI/Render All Rarity Icons")]
    public static void RenderAllRarityIcons()
    {{
        GameObject selected = Selection.activeGameObject;
        if (selected == null)
        {{
            EditorUtility.DisplayDialog("Icon Render", "Select a prefab in the Project window.", "OK");
            return;
        }}

        string[] rarities = {{ "Common", "Uncommon", "Rare", "Epic", "Legendary", "Corrupted" }};
        foreach (string rarity in rarities)
        {{
            RenderIcon(selected, rarity, DefaultIconSize);
        }}

        AssetDatabase.Refresh();
        EditorUtility.DisplayDialog("Icon Render", $"Rendered {{rarities.Length}} rarity variants.", "OK");
    }}

    /// <summary>
    /// Render a prefab as a 2D icon with specified rarity border.
    /// </summary>
    public static string RenderIcon(GameObject prefab, string rarity = "Common", int size = 0)
    {{
        if (size <= 0) size = DefaultIconSize;

        // Ensure output folder exists
        if (!Directory.Exists(OutputFolder))
            Directory.CreateDirectory(OutputFolder);

        // Create temporary render setup
        RenderTexture rt = new RenderTexture(size, size, 24, RenderTextureFormat.ARGB32);
        rt.antiAliasing = 4;

        // Create temporary camera
        GameObject camObj = new GameObject("_VB_IconCamera");
        Camera cam = camObj.AddComponent<Camera>();
        cam.backgroundColor = new Color(0f, 0f, 0f, 0f);
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.targetTexture = rt;
        cam.fieldOfView = 30f;
        cam.nearClipPlane = 0.01f;
        cam.farClipPlane = 100f;
        cam.transform.position = {cam_pos};
        cam.transform.eulerAngles = {cam_rot};

        // Instantiate item prefab
        GameObject instance = Object.Instantiate(prefab);
        instance.name = "_VB_IconTarget";
        instance.transform.position = Vector3.zero;
        instance.transform.rotation = Quaternion.identity;

        // Auto-frame: compute bounds and adjust camera
        Bounds bounds = GetCompositeBounds(instance);
        float maxExtent = Mathf.Max(bounds.extents.x, bounds.extents.y, bounds.extents.z);
        if (maxExtent > 0.01f)
        {{
            float distance = maxExtent * 3.5f / Mathf.Tan(cam.fieldOfView * 0.5f * Mathf.Deg2Rad);
            Vector3 dir = (cam.transform.position - bounds.center).normalized;
            cam.transform.position = bounds.center + dir * distance;
            cam.transform.LookAt(bounds.center);
        }}

        // Setup lighting
        SetupLighting("{light_setup}");

        // Render
        cam.Render();

        // Read back pixels
        RenderTexture.active = rt;
        Texture2D tex = new Texture2D(size, size, TextureFormat.RGBA32, false);
        tex.ReadPixels(new Rect(0, 0, size, size), 0, 0);
        tex.Apply();
        RenderTexture.active = null;

        // Post-process
        {"ApplyBackgroundGradient(tex);" if background_gradient else "// Background gradient disabled"}
        {"ApplyRarityBorder(tex, rarity);" if rarity_border else "// Rarity border disabled"}

        // Save
        string filename = $"{{prefab.name}}_{{rarity}}_{{size}}x{{size}}.png";
        string fullPath = Path.Combine(OutputFolder, filename);
        byte[] pngData = tex.EncodeToPNG();
        File.WriteAllBytes(fullPath, pngData);

        // Cleanup
        Object.DestroyImmediate(instance);
        Object.DestroyImmediate(camObj);
        CleanupLighting();
        rt.Release();
        Object.DestroyImmediate(rt);
        Object.DestroyImmediate(tex);

        return fullPath;
    }}

    private static Bounds GetCompositeBounds(GameObject obj)
    {{
        Renderer[] renderers = obj.GetComponentsInChildren<Renderer>();
        if (renderers.Length == 0)
            return new Bounds(obj.transform.position, Vector3.one * 0.5f);

        Bounds bounds = renderers[0].bounds;
        for (int i = 1; i < renderers.Length; i++)
            bounds.Encapsulate(renderers[i].bounds);
        return bounds;
    }}

    private static GameObject[] _tempLights;

    private static void SetupLighting(string preset)
    {{
        var lights = new System.Collections.Generic.List<GameObject>();

        switch (preset)
        {{
            case "three_point":
                lights.Add(CreateLight("Key", new Vector3(-2f, 3f, -1f), 1.2f, Color.white));
                lights.Add(CreateLight("Fill", new Vector3(2f, 2f, 1f), 0.5f, new Color(0.8f, 0.85f, 1f)));
                lights.Add(CreateLight("Rim", new Vector3(0f, 2f, 2f), 0.8f, new Color(1f, 0.9f, 0.7f)));
                break;
            case "dramatic":
                lights.Add(CreateLight("Key", new Vector3(-1f, 4f, -2f), 1.5f, new Color(1f, 0.85f, 0.6f)));
                lights.Add(CreateLight("Rim", new Vector3(1f, 1f, 2f), 0.6f, new Color(0.6f, 0.6f, 1f)));
                break;
            case "flat":
                lights.Add(CreateLight("Main", new Vector3(0f, 3f, -2f), 1.0f, Color.white));
                lights.Add(CreateLight("Ambient", new Vector3(0f, -1f, 0f), 0.4f, Color.white));
                break;
            case "rim":
                lights.Add(CreateLight("RimLeft", new Vector3(-2f, 2f, 1f), 1.0f, new Color(0.79f, 0.66f, 0.3f)));
                lights.Add(CreateLight("RimRight", new Vector3(2f, 2f, 1f), 1.0f, new Color(0.79f, 0.66f, 0.3f)));
                lights.Add(CreateLight("Fill", new Vector3(0f, 1f, -2f), 0.3f, Color.white));
                break;
        }}

        _tempLights = lights.ToArray();
    }}

    private static GameObject CreateLight(string name, Vector3 position, float intensity, Color color)
    {{
        GameObject lightObj = new GameObject($"_VB_IconLight_{{name}}");
        Light light = lightObj.AddComponent<Light>();
        light.type = LightType.Directional;
        lightObj.transform.position = position;
        lightObj.transform.LookAt(Vector3.zero);
        light.intensity = intensity;
        light.color = color;
        light.shadows = LightShadows.Soft;
        return lightObj;
    }}

    private static void CleanupLighting()
    {{
        if (_tempLights == null) return;
        foreach (var light in _tempLights)
        {{
            if (light != null)
                Object.DestroyImmediate(light);
        }}
        _tempLights = null;
    }}
{rarity_block}
{gradient_block}
}}
#endif
'''

    return {
        "script_path": "Assets/Scripts/Editor/VB_IconRenderPipeline.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Select an item prefab in Project window",
            "Use VeilBreakers > UI > Render Selected Item Icon menu",
            "Icons saved to Assets/Art/Icons/Generated/",
        ],
    }


# ---------------------------------------------------------------------------
# UIPOL-03: Cursor System
# ---------------------------------------------------------------------------


def generate_cursor_system_script(
    cursor_types: list[str] | None = None,
    detection_layers: str = "Default",
    cursor_size: int = 32,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for context-sensitive dark fantasy cursors.

    Creates a cursor system that auto-switches based on what the player
    hovers over, using raycast + layer/tag detection. Supports dark
    fantasy cursor themes: ornate pointer, gauntlet hand, branded
    crosshair, grab hand, speech bubble, and craft hammer.

    Args:
        cursor_types: List of cursor state names to include.
        detection_layers: Physics layer name for cursor raycast detection.
        cursor_size: Cursor texture size in pixels.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if cursor_types is None:
        cursor_types = ["default", "interact", "attack", "loot", "talk", "craft"]

    valid_types = {"default", "interact", "attack", "loot", "talk", "craft", "locked", "inspect"}
    cursor_types = [t for t in cursor_types if t in valid_types]
    if not cursor_types:
        cursor_types = ["default"]

    cursor_fields = []
    for ct in cursor_types:
        field_name = f"{ct}Cursor"
        cursor_fields.append(
            f'    [SerializeField] private Texture2D {field_name};'
        )

    cursor_fields_str = "\n".join(cursor_fields)

    cursor_hotspots = {
        "default": "new Vector2(0, 0)",
        "interact": "new Vector2(16, 0)",
        "attack": "new Vector2(16, 16)",
        "loot": "new Vector2(16, 8)",
        "talk": "new Vector2(0, 0)",
        "craft": "new Vector2(8, 24)",
        "locked": "new Vector2(16, 16)",
        "inspect": "new Vector2(16, 16)",
    }

    cursor_switch_cases = []
    for ct in cursor_types:
        hotspot = cursor_hotspots.get(ct, "Vector2.zero")
        cursor_switch_cases.append(
            f'            case CursorType.{ct.title()}:\n'
            f'                Cursor.SetCursor({ct}Cursor, {hotspot}, CursorMode.Auto);\n'
            f'                break;'
        )
    cursor_switch_str = "\n".join(cursor_switch_cases)

    enum_values = ", ".join([ct.title() for ct in cursor_types])

    detection_cases = []
    tag_mappings = {
        "interact": "Interactable",
        "attack": "Enemy",
        "loot": "Loot",
        "talk": "NPC",
        "craft": "CraftStation",
        "locked": "Locked",
        "inspect": "Inspectable",
    }
    for ct in cursor_types:
        if ct == "default":
            continue
        tag = tag_mappings.get(ct, ct.title())
        detection_cases.append(
            f'            if (hit.collider.CompareTag("{tag}"))\n'
            f'                return CursorType.{ct.title()};'
        )
    detection_cases_str = "\n".join(detection_cases)

    script = f'''// VeilBreakers Auto-Generated: Context-Sensitive Cursor System
// Dark fantasy themed cursors that change based on hover target
using UnityEngine;

/// <summary>
/// Context-sensitive cursor system for dark fantasy UI. Auto-switches cursor
/// texture based on what the player hovers (enemies, NPCs, loot, etc).
/// Uses raycast detection with tag-based identification.
/// </summary>
public class VB_CursorSystem : MonoBehaviour
{{
    public enum CursorType {{ {enum_values} }}

    [Header("Cursor Textures (assign {cursor_size}x{cursor_size} textures)")]
{cursor_fields_str}

    [Header("Detection")]
    [SerializeField] private Camera mainCamera;
    [SerializeField] private LayerMask detectionLayers = ~0;
    [SerializeField] private float raycastDistance = 100f;

    [Header("Settings")]
    [SerializeField] private bool autoDetect = true;
    [SerializeField] private float detectionInterval = 0.05f;

    private CursorType _currentType = CursorType.{cursor_types[0].title()};
    private float _nextDetectionTime;

    private void Start()
    {{
        if (mainCamera == null)
            mainCamera = Camera.main;
        SetCursor(CursorType.{cursor_types[0].title()});
    }}

    private void Update()
    {{
        if (!autoDetect || mainCamera == null) return;
        if (Time.time < _nextDetectionTime) return;
        _nextDetectionTime = Time.time + detectionInterval;

        CursorType detected = DetectCursorType();
        if (detected != _currentType)
            SetCursor(detected);
    }}

    /// <summary>
    /// Set the cursor to a specific type.
    /// </summary>
    public void SetCursor(CursorType type)
    {{
        _currentType = type;
        switch (type)
        {{
{cursor_switch_str}
        }}
    }}

    /// <summary>
    /// Get the current cursor type.
    /// </summary>
    public CursorType GetCurrentCursorType() => _currentType;

    private CursorType DetectCursorType()
    {{
        Ray ray = mainCamera.ScreenPointToRay(Input.mousePosition);
        if (Physics.Raycast(ray, out RaycastHit hit, raycastDistance, detectionLayers))
        {{
{detection_cases_str}
        }}
        return CursorType.{cursor_types[0].title()};
    }}

    /// <summary>
    /// Enable or disable auto-detection at runtime.
    /// </summary>
    public void SetAutoDetect(bool enabled)
    {{
        autoDetect = enabled;
    }}

    /// <summary>
    /// Force reset to default cursor.
    /// </summary>
    public void ResetToDefault()
    {{
        SetCursor(CursorType.{cursor_types[0].title()});
    }}

    private void OnDisable()
    {{
        Cursor.SetCursor(null, Vector2.zero, CursorMode.Auto);
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/UI/VB_CursorSystem.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            f"Create {cursor_size}x{cursor_size} cursor textures for each state",
            "Set texture import type to 'Cursor' in Unity",
            "Add VB_CursorSystem to your player/camera and assign cursor textures",
            "Tag scene objects: Enemy, Interactable, Loot, NPC, CraftStation",
        ],
    }


# ---------------------------------------------------------------------------
# UIPOL-04: Tooltip System
# ---------------------------------------------------------------------------


def generate_tooltip_system_script(
    tooltip_style: str = "dark_fantasy",
    show_comparison: bool = True,
    show_lore: bool = True,
    fade_duration: float = 0.2,
    max_width: int = 350,
) -> dict[str, Any]:
    """Generate C# + UXML/USS for a rich tooltip system.

    Creates tooltips with item name (rarity colored), icon, stats with
    color-coded values, equipment comparison with stat deltas, lore text,
    smart positioning, and PrimeTween fade animations.

    Args:
        tooltip_style: Visual style -- dark_fantasy, minimal, ornate.
        show_comparison: Whether to show equipment stat comparison.
        show_lore: Whether to show lore text section.
        fade_duration: Fade in/out animation duration.
        max_width: Maximum tooltip width in pixels.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    valid_styles = {"dark_fantasy", "minimal", "ornate"}
    if tooltip_style not in valid_styles:
        tooltip_style = "dark_fantasy"

    comparison_block = ""
    if show_comparison:
        comparison_block = '''
    /// <summary>
    /// Show equipment comparison between current and hovered item.
    /// </summary>
    public void ShowComparison(ItemTooltipData current, ItemTooltipData hovered)
    {
        if (_comparisonContainer == null) return;
        _comparisonContainer.Clear();
        _comparisonContainer.style.display = DisplayStyle.Flex;

        var header = new Label("-- Compared to Equipped --");
        header.AddToClassList("vb-tooltip__comparison-header");
        _comparisonContainer.Add(header);

        // Compare stats
        if (current.stats != null && hovered.stats != null)
        {
            foreach (var kvp in hovered.stats)
            {
                float currentVal = 0f;
                if (current.stats.ContainsKey(kvp.Key))
                    currentVal = current.stats[kvp.Key];

                float delta = kvp.Value - currentVal;
                if (Mathf.Abs(delta) < 0.01f) continue;

                var statLine = new VisualElement();
                statLine.AddToClassList("vb-tooltip__stat-line");

                string arrow = delta > 0 ? "\\u25B2" : "\\u25BC";
                string sign = delta > 0 ? "+" : "";
                Color color = delta > 0
                    ? new Color(0.18f, 0.8f, 0.44f)     // Green for better
                    : new Color(0.91f, 0.3f, 0.24f);     // Red for worse

                var label = new Label($"{kvp.Key}: {sign}{delta:F1} {arrow}");
                label.AddToClassList("vb-tooltip__stat-delta");
                label.style.color = color;
                statLine.Add(label);
                _comparisonContainer.Add(statLine);
            }
        }
    }

    private void HideComparison()
    {
        if (_comparisonContainer != null)
            _comparisonContainer.style.display = DisplayStyle.None;
    }'''

    lore_block = ""
    lore_show_call = "        // Lore display disabled"
    lore_hide_call = "        // Lore hide disabled"
    if show_lore:
        lore_show_call = (
            "        if (showLore && !string.IsNullOrEmpty(data.loreText))\n"
            "            ShowLoreText(data.loreText);\n"
            "        else\n"
            "            HideLoreText();"
        )
        lore_hide_call = "        HideLoreText();"
        lore_block = '''
    private void ShowLoreText(string loreText)
    {
        if (string.IsNullOrEmpty(loreText) || _loreLabel == null) return;
        _loreLabel.text = loreText;
        _loreLabel.style.display = DisplayStyle.Flex;
    }

    private void HideLoreText()
    {
        if (_loreLabel != null)
            _loreLabel.style.display = DisplayStyle.None;
    }'''

    script = f'''// VeilBreakers Auto-Generated: Rich Tooltip System
// Dark fantasy tooltips with item stats, comparison, and lore
using UnityEngine;
using UnityEngine.UIElements;
using System.Collections.Generic;

/// <summary>
/// Rich tooltip system with rarity-colored item names, stat display,
/// equipment comparison with delta arrows, and lore text.
/// Uses UI Toolkit for rendering and PrimeTween for animations.
/// </summary>
public class VB_TooltipSystem : MonoBehaviour
{{
    [Header("Configuration")]
    [SerializeField] private UIDocument uiDocument;
    [SerializeField] private float fadeDuration = {fade_duration}f;
    [SerializeField] private int maxWidth = {max_width};
    [SerializeField] private Vector2 cursorOffset = new Vector2(16f, 16f);
    [SerializeField] private bool showComparison = {str(show_comparison).lower()};
    [SerializeField] private bool showLore = {str(show_lore).lower()};

    // Rarity colors
    private static readonly Dictionary<string, Color> RarityColors = new Dictionary<string, Color>
    {{
        {{ "Common", new Color(0.5f, 0.5f, 0.5f) }},
        {{ "Uncommon", new Color(0.18f, 0.8f, 0.44f) }},
        {{ "Rare", new Color(0.2f, 0.6f, 0.86f) }},
        {{ "Epic", new Color(0.61f, 0.35f, 0.71f) }},
        {{ "Legendary", new Color(0.95f, 0.77f, 0.06f) }},
        {{ "Corrupted", new Color(0.91f, 0.3f, 0.24f) }},
    }};

    private VisualElement _root;
    private VisualElement _tooltipContainer;
    private Label _nameLabel;
    private Label _typeLabel;
    private VisualElement _statsContainer;
    private VisualElement _comparisonContainer;
    private Label _loreLabel;
    private VisualElement _iconElement;
    private bool _isVisible;

    /// <summary>
    /// Data class for tooltip display.
    /// </summary>
    [System.Serializable]
    public class ItemTooltipData
    {{
        public string itemName = "Unknown Item";
        public string itemType = "Miscellaneous";
        public string rarity = "Common";
        public string description = "";
        public string loreText = "";
        public Texture2D icon;
        public Dictionary<string, float> stats;
    }}

    private void OnEnable()
    {{
        if (uiDocument == null)
            uiDocument = GetComponent<UIDocument>();
        if (uiDocument == null) return;

        _root = uiDocument.rootVisualElement;
        BuildTooltipStructure();
        HideTooltip();
    }}

    private void BuildTooltipStructure()
    {{
        _tooltipContainer = new VisualElement();
        _tooltipContainer.AddToClassList("vb-tooltip");
        _tooltipContainer.style.position = Position.Absolute;
        _tooltipContainer.style.maxWidth = maxWidth;
        _tooltipContainer.style.backgroundColor = new Color(0.1f, 0.1f, 0.18f, 0.95f);
        _tooltipContainer.style.borderTopWidth = 2;
        _tooltipContainer.style.borderBottomWidth = 2;
        _tooltipContainer.style.borderLeftWidth = 2;
        _tooltipContainer.style.borderRightWidth = 2;
        _tooltipContainer.style.borderTopColor = new Color(0.79f, 0.66f, 0.3f);
        _tooltipContainer.style.borderBottomColor = new Color(0.79f, 0.66f, 0.3f);
        _tooltipContainer.style.borderLeftColor = new Color(0.79f, 0.66f, 0.3f);
        _tooltipContainer.style.borderRightColor = new Color(0.79f, 0.66f, 0.3f);
        _tooltipContainer.style.borderTopLeftRadius = 4;
        _tooltipContainer.style.borderTopRightRadius = 4;
        _tooltipContainer.style.borderBottomLeftRadius = 4;
        _tooltipContainer.style.borderBottomRightRadius = 4;
        _tooltipContainer.style.paddingTop = 8;
        _tooltipContainer.style.paddingBottom = 8;
        _tooltipContainer.style.paddingLeft = 12;
        _tooltipContainer.style.paddingRight = 12;

        // Header row: icon + name/type
        var headerRow = new VisualElement();
        headerRow.style.flexDirection = FlexDirection.Row;
        headerRow.style.marginBottom = 6;

        _iconElement = new VisualElement();
        _iconElement.style.width = 40;
        _iconElement.style.height = 40;
        _iconElement.style.marginRight = 8;
        headerRow.Add(_iconElement);

        var nameColumn = new VisualElement();
        _nameLabel = new Label();
        _nameLabel.AddToClassList("vb-tooltip__name");
        _nameLabel.style.fontSize = 14;
        _nameLabel.style.unityFontStyleAndWeight = FontStyle.Bold;
        nameColumn.Add(_nameLabel);

        _typeLabel = new Label();
        _typeLabel.AddToClassList("vb-tooltip__type");
        _typeLabel.style.fontSize = 11;
        _typeLabel.style.color = new Color(0.6f, 0.6f, 0.7f);
        nameColumn.Add(_typeLabel);

        headerRow.Add(nameColumn);
        _tooltipContainer.Add(headerRow);

        // Divider
        var divider = new VisualElement();
        divider.style.height = 1;
        divider.style.backgroundColor = new Color(0.79f, 0.66f, 0.3f, 0.4f);
        divider.style.marginTop = 4;
        divider.style.marginBottom = 4;
        _tooltipContainer.Add(divider);

        // Stats container
        _statsContainer = new VisualElement();
        _statsContainer.AddToClassList("vb-tooltip__stats");
        _tooltipContainer.Add(_statsContainer);

        // Comparison container
        _comparisonContainer = new VisualElement();
        _comparisonContainer.AddToClassList("vb-tooltip__comparison");
        _comparisonContainer.style.display = DisplayStyle.None;
        _tooltipContainer.Add(_comparisonContainer);

        // Lore label
        _loreLabel = new Label();
        _loreLabel.AddToClassList("vb-tooltip__lore");
        _loreLabel.style.fontSize = 11;
        _loreLabel.style.color = new Color(0.83f, 0.77f, 0.66f);
        _loreLabel.style.unityFontStyleAndWeight = FontStyle.Italic;
        _loreLabel.style.whiteSpace = WhiteSpace.Normal;
        _loreLabel.style.marginTop = 6;
        _loreLabel.style.display = DisplayStyle.None;
        _tooltipContainer.Add(_loreLabel);

        _root.Add(_tooltipContainer);
    }}

    /// <summary>
    /// Show tooltip with item data at the current cursor position.
    /// </summary>
    public void ShowTooltip(ItemTooltipData data)
    {{
        if (data == null || _tooltipContainer == null) return;

        // Set name with rarity color
        _nameLabel.text = data.itemName;
        if (RarityColors.TryGetValue(data.rarity, out Color rarityColor))
            _nameLabel.style.color = rarityColor;
        else
            _nameLabel.style.color = Color.white;

        _typeLabel.text = $"{{data.itemType}} - {{data.rarity}}";

        // Set icon
        if (data.icon != null)
        {{
            _iconElement.style.backgroundImage = data.icon;
            _iconElement.style.display = DisplayStyle.Flex;
        }}
        else
        {{
            _iconElement.style.display = DisplayStyle.None;
        }}

        // Populate stats
        _statsContainer.Clear();
        if (data.stats != null)
        {{
            foreach (var kvp in data.stats)
            {{
                var statLine = new VisualElement();
                statLine.AddToClassList("vb-tooltip__stat-line");
                statLine.style.flexDirection = FlexDirection.Row;
                statLine.style.justifyContent = Justify.SpaceBetween;

                var statName = new Label(kvp.Key);
                statName.style.color = new Color(0.7f, 0.7f, 0.8f);
                statName.style.fontSize = 12;
                statLine.Add(statName);

                var statValue = new Label(kvp.Value.ToString("F1"));
                statValue.style.color = Color.white;
                statValue.style.fontSize = 12;
                statLine.Add(statValue);

                _statsContainer.Add(statLine);
            }}
        }}

        // Lore text
{lore_show_call}

        // Position and show
        _tooltipContainer.style.display = DisplayStyle.Flex;
        _tooltipContainer.style.opacity = 0f;
        _isVisible = true;
        UpdatePosition();

        // Fade in via PrimeTween
        // Tween.UIAlpha(_tooltipContainer, 0f, 1f, fadeDuration);
        _tooltipContainer.schedule.Execute(() =>
        {{
            _tooltipContainer.style.opacity = 1f;
        }}).StartingIn((long)(fadeDuration * 1000));
    }}

    /// <summary>
    /// Hide the tooltip with fade-out animation.
    /// </summary>
    public void HideTooltip()
    {{
        _isVisible = false;
        if (_tooltipContainer != null)
        {{
            _tooltipContainer.style.display = DisplayStyle.None;
            _tooltipContainer.style.opacity = 0f;
        }}
{"        HideComparison();" if show_comparison else ""}
{lore_hide_call}
    }}

    private void Update()
    {{
        if (_isVisible)
            UpdatePosition();
    }}

    private void UpdatePosition()
    {{
        if (_tooltipContainer == null) return;

        Vector2 mousePos = Input.mousePosition;
        // Convert screen coords to UI Toolkit coords (y-flip)
        float screenH = Screen.height;
        float x = mousePos.x + cursorOffset.x;
        float y = screenH - mousePos.y + cursorOffset.y;

        // Clamp to screen bounds
        float tooltipW = _tooltipContainer.resolvedStyle.width;
        float tooltipH = _tooltipContainer.resolvedStyle.height;
        if (float.IsNaN(tooltipW)) tooltipW = maxWidth;
        if (float.IsNaN(tooltipH)) tooltipH = 200f;

        if (x + tooltipW > Screen.width)
            x = mousePos.x - tooltipW - cursorOffset.x;
        if (y + tooltipH > screenH)
            y = screenH - mousePos.y - tooltipH - cursorOffset.y;

        x = Mathf.Max(0f, x);
        y = Mathf.Max(0f, y);

        _tooltipContainer.style.left = x;
        _tooltipContainer.style.top = y;
    }}
{comparison_block}
{lore_block}

    /// <summary>
    /// Check if the tooltip is currently visible.
    /// </summary>
    public bool IsVisible() => _isVisible;
}}
'''

    uss_content = f"""/* VeilBreakers Dark Fantasy Tooltip Styles */
.vb-tooltip {{
    background-color: rgba(26, 26, 46, 0.95);
    border-width: 2px;
    border-color: {VB_COLORS['rich_gold']};
    border-radius: 4px;
    padding: 8px 12px;
    max-width: {max_width}px;
}}

.vb-tooltip__name {{
    font-size: 14px;
    -unity-font-style: bold;
    letter-spacing: 1px;
}}

.vb-tooltip__type {{
    font-size: 11px;
    color: {VB_COLORS['steel_grey']};
}}

.vb-tooltip__stat-line {{
    flex-direction: row;
    justify-content: space-between;
    padding: 1px 0;
}}

.vb-tooltip__stat-delta {{
    font-size: 12px;
    -unity-font-style: bold;
}}

.vb-tooltip__comparison-header {{
    font-size: 11px;
    color: {VB_COLORS['parchment']};
    -unity-font-style: italic;
    margin-top: 6px;
    margin-bottom: 4px;
    -unity-text-align: middle-center;
}}

.vb-tooltip__lore {{
    font-size: 11px;
    color: {VB_COLORS['parchment']};
    -unity-font-style: italic;
    margin-top: 6px;
    white-space: normal;
}}"""

    return {
        "script_path": "Assets/Scripts/Runtime/UI/VB_TooltipSystem.cs",
        "script_content": script,
        "uss_content": uss_content,
        "uss_path": "Assets/UI/Styles/VB_Tooltip.uss",
        "next_steps": [
            "Save the C# script and USS file to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Add VB_TooltipSystem to a UIDocument in your scene",
            "Create ItemTooltipData instances and call ShowTooltip(data)",
            "For comparison, call ShowComparison(equippedData, hoveredData)",
        ],
    }


# ---------------------------------------------------------------------------
# UIPOL-05: Radial Menu
# ---------------------------------------------------------------------------


def generate_radial_menu_script(
    segment_count: int = 8,
    radius: float = 150.0,
    menu_type: str = "ability",
    trigger_key: str = "Tab",
) -> dict[str, Any]:
    """Generate C# MonoBehaviour + UXML for radial ability/item wheel.

    Creates a circular menu with configurable segments, icon + hotkey
    labels, animated expand/collapse (PrimeTween), mouse-direction
    selection, and keyboard shortcut support.

    Args:
        segment_count: Number of menu segments (4-12).
        radius: Radius of the radial menu in pixels.
        menu_type: Type -- ability, item, spell.
        trigger_key: KeyCode name to toggle the menu.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    segment_count = max(4, min(12, segment_count))

    valid_types = {"ability", "item", "spell"}
    if menu_type not in valid_types:
        menu_type = "ability"

    script = f'''// VeilBreakers Auto-Generated: Radial Menu System
// Circular ability/item wheel with mouse-direction selection
using UnityEngine;
using UnityEngine.UIElements;
using System;
using System.Collections.Generic;

/// <summary>
/// Radial menu for quick-selecting abilities, items, or spells.
/// Features animated expand/collapse, mouse-direction selection,
/// keyboard shortcuts, and dark fantasy styling.
/// </summary>
public class VB_RadialMenu : MonoBehaviour
{{
    [Header("Configuration")]
    [SerializeField] private UIDocument uiDocument;
    [SerializeField] private int segmentCount = {segment_count};
    [SerializeField] private float radius = {radius}f;
    [SerializeField] private KeyCode triggerKey = KeyCode.{trigger_key};
    [SerializeField] private string menuType = "{menu_type}";

    [Header("Animation")]
    [SerializeField] private float expandDuration = 0.25f;
    [SerializeField] private float collapseDuration = 0.15f;

    [Header("Visuals")]
    [SerializeField] private Color normalColor = new Color(0.1f, 0.1f, 0.18f, 0.9f);
    [SerializeField] private Color hoverColor = new Color(0.79f, 0.66f, 0.3f, 0.5f);
    [SerializeField] private Color selectedColor = new Color(0.79f, 0.66f, 0.3f, 0.8f);

    /// <summary>
    /// Data for each radial menu segment.
    /// </summary>
    [System.Serializable]
    public class RadialSegment
    {{
        public string name = "Empty";
        public Texture2D icon;
        public string hotkeyLabel = "";
        public bool isEnabled = true;
        public float cooldownRemaining = 0f;
        public float cooldownTotal = 0f;
    }}

    public event Action<int> OnSegmentSelected;
    public event Action OnMenuOpened;
    public event Action OnMenuClosed;

    private VisualElement _root;
    private VisualElement _menuContainer;
    private VisualElement _centerElement;
    private List<VisualElement> _segments = new List<VisualElement>();
    private List<RadialSegment> _segmentData = new List<RadialSegment>();
    private int _hoveredIndex = -1;
    private int _selectedIndex = -1;
    private bool _isOpen;
    private float _currentScale;

    private void OnEnable()
    {{
        if (uiDocument == null)
            uiDocument = GetComponent<UIDocument>();
        if (uiDocument == null) return;

        _root = uiDocument.rootVisualElement;
        InitializeSegments();
        BuildMenu();
        CloseMenu();
    }}

    private void InitializeSegments()
    {{
        _segmentData.Clear();
        for (int i = 0; i < segmentCount; i++)
        {{
            _segmentData.Add(new RadialSegment
            {{
                name = $"Slot {{i + 1}}",
                hotkeyLabel = (i + 1).ToString(),
            }});
        }}
    }}

    /// <summary>
    /// Set data for a specific segment.
    /// </summary>
    public void SetSegment(int index, RadialSegment data)
    {{
        if (index < 0 || index >= _segmentData.Count) return;
        _segmentData[index] = data;
        if (_isOpen) RefreshSegmentVisuals(index);
    }}

    private void BuildMenu()
    {{
        if (_menuContainer != null)
            _menuContainer.RemoveFromHierarchy();

        _menuContainer = new VisualElement();
        _menuContainer.AddToClassList("vb-radial");
        _menuContainer.style.position = Position.Absolute;
        _menuContainer.style.width = radius * 2;
        _menuContainer.style.height = radius * 2;

        // Center the menu on screen
        _menuContainer.style.left = Length.Percent(50);
        _menuContainer.style.top = Length.Percent(50);
        _menuContainer.style.translate = new Translate(
            new Length(-radius, LengthUnit.Pixel),
            new Length(-radius, LengthUnit.Pixel));

        // Center element (label for selected item)
        _centerElement = new VisualElement();
        _centerElement.AddToClassList("vb-radial__center");
        _centerElement.style.position = Position.Absolute;
        _centerElement.style.left = radius - 40;
        _centerElement.style.top = radius - 40;
        _centerElement.style.width = 80;
        _centerElement.style.height = 80;
        _centerElement.style.borderTopLeftRadius = 40;
        _centerElement.style.borderTopRightRadius = 40;
        _centerElement.style.borderBottomLeftRadius = 40;
        _centerElement.style.borderBottomRightRadius = 40;
        _centerElement.style.backgroundColor = normalColor;
        _centerElement.style.borderTopWidth = 2;
        _centerElement.style.borderBottomWidth = 2;
        _centerElement.style.borderLeftWidth = 2;
        _centerElement.style.borderRightWidth = 2;
        _centerElement.style.borderTopColor = new Color(0.79f, 0.66f, 0.3f);
        _centerElement.style.borderBottomColor = new Color(0.79f, 0.66f, 0.3f);
        _centerElement.style.borderLeftColor = new Color(0.79f, 0.66f, 0.3f);
        _centerElement.style.borderRightColor = new Color(0.79f, 0.66f, 0.3f);

        var centerLabel = new Label(menuType.ToUpper());
        centerLabel.style.color = new Color(0.79f, 0.66f, 0.3f);
        centerLabel.style.fontSize = 10;
        centerLabel.style.unityTextAlign = TextAnchor.MiddleCenter;
        centerLabel.style.width = Length.Percent(100);
        centerLabel.style.height = Length.Percent(100);
        _centerElement.Add(centerLabel);
        _menuContainer.Add(_centerElement);

        // Create segments around the circle
        _segments.Clear();
        float angleStep = 360f / segmentCount;
        float segmentSize = 56f;

        for (int i = 0; i < segmentCount; i++)
        {{
            float angle = (angleStep * i - 90f) * Mathf.Deg2Rad;
            float x = radius + Mathf.Cos(angle) * (radius * 0.65f) - segmentSize / 2f;
            float y = radius + Mathf.Sin(angle) * (radius * 0.65f) - segmentSize / 2f;

            var segment = new VisualElement();
            segment.AddToClassList("vb-radial__segment");
            segment.style.position = Position.Absolute;
            segment.style.left = x;
            segment.style.top = y;
            segment.style.width = segmentSize;
            segment.style.height = segmentSize;
            segment.style.borderTopLeftRadius = segmentSize / 2f;
            segment.style.borderTopRightRadius = segmentSize / 2f;
            segment.style.borderBottomLeftRadius = segmentSize / 2f;
            segment.style.borderBottomRightRadius = segmentSize / 2f;
            segment.style.backgroundColor = normalColor;
            segment.style.borderTopWidth = 1;
            segment.style.borderBottomWidth = 1;
            segment.style.borderLeftWidth = 1;
            segment.style.borderRightWidth = 1;
            segment.style.borderTopColor = new Color(0.79f, 0.66f, 0.3f, 0.6f);
            segment.style.borderBottomColor = new Color(0.79f, 0.66f, 0.3f, 0.6f);
            segment.style.borderLeftColor = new Color(0.79f, 0.66f, 0.3f, 0.6f);
            segment.style.borderRightColor = new Color(0.79f, 0.66f, 0.3f, 0.6f);

            // Hotkey label
            var hotkeyLabel = new Label(_segmentData[i].hotkeyLabel);
            hotkeyLabel.AddToClassList("vb-radial__hotkey");
            hotkeyLabel.style.position = Position.Absolute;
            hotkeyLabel.style.bottom = -2;
            hotkeyLabel.style.right = 2;
            hotkeyLabel.style.fontSize = 9;
            hotkeyLabel.style.color = new Color(0.79f, 0.66f, 0.3f, 0.8f);
            segment.Add(hotkeyLabel);

            // Name label
            var nameLabel = new Label(_segmentData[i].name);
            nameLabel.AddToClassList("vb-radial__name");
            nameLabel.style.fontSize = 9;
            nameLabel.style.color = Color.white;
            nameLabel.style.unityTextAlign = TextAnchor.MiddleCenter;
            nameLabel.style.width = Length.Percent(100);
            nameLabel.style.height = Length.Percent(100);
            segment.Add(nameLabel);

            _segments.Add(segment);
            _menuContainer.Add(segment);
        }}

        _root.Add(_menuContainer);
    }}

    private void Update()
    {{
        // Toggle menu
        if (Input.GetKeyDown(triggerKey))
        {{
            if (_isOpen) CloseMenu();
            else OpenMenu();
        }}

        // Keyboard shortcuts (1-9)
        if (_isOpen)
        {{
            for (int i = 0; i < Mathf.Min(segmentCount, 9); i++)
            {{
                if (Input.GetKeyDown(KeyCode.Alpha1 + i))
                {{
                    SelectSegment(i);
                    CloseMenu();
                    return;
                }}
            }}

            // Mouse direction detection
            UpdateMouseSelection();
        }}
    }}

    private void UpdateMouseSelection()
    {{
        Vector2 center = new Vector2(Screen.width / 2f, Screen.height / 2f);
        Vector2 mousePos = Input.mousePosition;
        Vector2 direction = mousePos - center;
        float distance = direction.magnitude;

        if (distance < 30f)
        {{
            SetHoveredIndex(-1);
            return;
        }}

        // Calculate angle and determine segment
        float angle = Mathf.Atan2(direction.y, direction.x) * Mathf.Rad2Deg;
        angle = (angle + 90f + 360f) % 360f;
        float angleStep = 360f / segmentCount;
        int index = Mathf.FloorToInt((angle + angleStep / 2f) % 360f / angleStep);
        index = Mathf.Clamp(index, 0, segmentCount - 1);

        SetHoveredIndex(index);

        // Click to select
        if (Input.GetMouseButtonDown(0) && _hoveredIndex >= 0)
        {{
            SelectSegment(_hoveredIndex);
            CloseMenu();
        }}
    }}

    private void SetHoveredIndex(int index)
    {{
        if (index == _hoveredIndex) return;

        // Reset previous hover
        if (_hoveredIndex >= 0 && _hoveredIndex < _segments.Count)
            _segments[_hoveredIndex].style.backgroundColor = normalColor;

        _hoveredIndex = index;

        // Apply hover effect
        if (_hoveredIndex >= 0 && _hoveredIndex < _segments.Count)
            _segments[_hoveredIndex].style.backgroundColor = hoverColor;
    }}

    private void SelectSegment(int index)
    {{
        if (index < 0 || index >= _segmentData.Count) return;
        if (!_segmentData[index].isEnabled) return;

        _selectedIndex = index;
        OnSegmentSelected?.Invoke(index);
    }}

    /// <summary>
    /// Open the radial menu with expand animation.
    /// </summary>
    public void OpenMenu()
    {{
        if (_menuContainer == null) return;
        _isOpen = true;
        _menuContainer.style.display = DisplayStyle.Flex;
        _menuContainer.style.opacity = 1f;
        // PrimeTween: Tween.Scale(_menuContainer, 0f, 1f, expandDuration);
        _menuContainer.transform.scale = Vector3.one;
        OnMenuOpened?.Invoke();
    }}

    /// <summary>
    /// Close the radial menu with collapse animation.
    /// </summary>
    public void CloseMenu()
    {{
        _isOpen = false;
        _hoveredIndex = -1;
        if (_menuContainer != null)
        {{
            _menuContainer.style.display = DisplayStyle.None;
        }}
        OnMenuClosed?.Invoke();
    }}

    /// <summary>
    /// Check if the radial menu is currently open.
    /// </summary>
    public bool IsOpen() => _isOpen;

    /// <summary>
    /// Get the currently selected segment index (-1 if none).
    /// </summary>
    public int GetSelectedIndex() => _selectedIndex;

    private void RefreshSegmentVisuals(int index)
    {{
        if (index < 0 || index >= _segments.Count) return;
        var data = _segmentData[index];
        var segment = _segments[index];

        // Update name label
        var nameLabel = segment.Q<Label>(className: "vb-radial__name");
        if (nameLabel != null) nameLabel.text = data.name;

        // Update hotkey label
        var hotkeyLabel = segment.Q<Label>(className: "vb-radial__hotkey");
        if (hotkeyLabel != null) hotkeyLabel.text = data.hotkeyLabel;

        // Update enabled state
        segment.style.opacity = data.isEnabled ? 1f : 0.4f;
    }}
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/UI/VB_RadialMenu.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Add VB_RadialMenu to a UIDocument in your scene",
            f"Press {trigger_key} to toggle the radial menu",
            "Call SetSegment(index, data) to populate with abilities/items",
            "Subscribe to OnSegmentSelected event for selection handling",
        ],
    }


# ---------------------------------------------------------------------------
# UIPOL-06: Notification System
# ---------------------------------------------------------------------------


def generate_notification_system_script(
    max_visible: int = 5,
    auto_dismiss_seconds: float = 4.0,
    position: str = "top_right",
    toast_types: list[str] | None = None,
) -> dict[str, Any]:
    """Generate C# MonoBehaviour for toast notification system.

    Creates a queue-based notification system with typed toasts,
    priority handling, slide-in/fade-out animations via PrimeTween,
    and configurable positioning.

    Args:
        max_visible: Maximum notifications visible at once.
        auto_dismiss_seconds: Time before auto-dismiss.
        position: Screen position -- top_right, top_left, bottom_right, bottom_center.
        toast_types: List of toast type names.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if toast_types is None:
        toast_types = ["quest_update", "item_pickup", "level_up", "achievement", "warning", "system"]

    valid_positions = {"top_right", "top_left", "bottom_right", "bottom_center"}
    if position not in valid_positions:
        position = "top_right"

    enum_values = ", ".join([t.title().replace("_", "") for t in toast_types])

    # Position-based anchor styling (C# UI Toolkit property assignments)
    position_styles = {
        "top_right": [
            "_toastContainer.style.right = 20;",
            "_toastContainer.style.top = 20;",
            "_toastContainer.style.flexDirection = FlexDirection.Column;",
        ],
        "top_left": [
            "_toastContainer.style.left = 20;",
            "_toastContainer.style.top = 20;",
            "_toastContainer.style.flexDirection = FlexDirection.Column;",
        ],
        "bottom_right": [
            "_toastContainer.style.right = 20;",
            "_toastContainer.style.bottom = 20;",
            "_toastContainer.style.flexDirection = FlexDirection.ColumnReverse;",
        ],
        "bottom_center": [
            "_toastContainer.style.left = new Length(50, LengthUnit.Percent);",
            "_toastContainer.style.translate = new Translate(new Length(-50, LengthUnit.Percent), 0);",
            "_toastContainer.style.bottom = 20;",
            "_toastContainer.style.flexDirection = FlexDirection.ColumnReverse;",
        ],
    }
    pos_code = "\n        ".join(position_styles[position])

    # Type-specific colors
    type_color_cases = []
    type_colors = {
        "quest_update": ("0.95f, 0.77f, 0.06f", "Quest Updated"),
        "item_pickup": ("0.18f, 0.8f, 0.44f", "Item Acquired"),
        "level_up": ("0.61f, 0.35f, 0.71f", "Level Up!"),
        "achievement": ("0.95f, 0.77f, 0.06f", "Achievement"),
        "warning": ("0.91f, 0.3f, 0.24f", "Warning"),
        "system": ("0.5f, 0.5f, 0.6f", "System"),
    }
    for tt in toast_types:
        colors, _label = type_colors.get(tt, ("0.7f, 0.7f, 0.7f", tt.title()))
        case_name = tt.title().replace("_", "")
        type_color_cases.append(
            f'            case ToastType.{case_name}: return new Color({colors});'
        )
    type_color_switch = "\n".join(type_color_cases)

    script = f'''// VeilBreakers Auto-Generated: Notification / Toast System
// Queue-based toast notifications with priority and animations
using UnityEngine;
using UnityEngine.UIElements;
using System.Collections.Generic;

/// <summary>
/// Toast notification system with typed messages, priority queue,
/// slide-in/fade-out animations, and auto-dismiss timer.
/// Uses UI Toolkit for rendering.
/// </summary>
public class VB_NotificationSystem : MonoBehaviour
{{
    public enum ToastType {{ {enum_values} }}

    public enum ToastPriority {{ Low, Normal, High, Critical }}

    [Header("Configuration")]
    [SerializeField] private UIDocument uiDocument;
    [SerializeField] private int maxVisible = {max_visible};
    [SerializeField] private float autoDismissSeconds = {auto_dismiss_seconds}f;

    [Header("Animation")]
    [SerializeField] private float slideInDuration = 0.3f;
    [SerializeField] private float fadeOutDuration = 0.5f;

    /// <summary>
    /// Data class for a toast notification.
    /// </summary>
    public class ToastData
    {{
        public ToastType type;
        public ToastPriority priority;
        public string title;
        public string description;
        public Texture2D icon;
        public float displayTime;
        public float timestamp;
    }}

    private VisualElement _root;
    private VisualElement _toastContainer;
    private Queue<ToastData> _pendingQueue = new Queue<ToastData>();
    private List<ToastData> _activeToasts = new List<ToastData>();
    private List<VisualElement> _activeElements = new List<VisualElement>();

    private void OnEnable()
    {{
        if (uiDocument == null)
            uiDocument = GetComponent<UIDocument>();
        if (uiDocument == null) return;

        _root = uiDocument.rootVisualElement;
        BuildContainer();
    }}

    private void BuildContainer()
    {{
        _toastContainer = new VisualElement();
        _toastContainer.AddToClassList("vb-notification-container");
        _toastContainer.style.position = Position.Absolute;
        {pos_code}
        _toastContainer.style.width = 320;

        _root.Add(_toastContainer);
    }}

    /// <summary>
    /// Show a toast notification.
    /// </summary>
    public void ShowToast(ToastType type, string title, string description = "",
        Texture2D icon = null, ToastPriority priority = ToastPriority.Normal)
    {{
        var data = new ToastData
        {{
            type = type,
            priority = priority,
            title = title,
            description = description,
            icon = icon,
            displayTime = autoDismissSeconds,
            timestamp = Time.time,
        }};

        // Critical priority: display immediately
        if (priority == ToastPriority.Critical)
        {{
            if (_activeToasts.Count >= maxVisible)
                DismissOldest();
            DisplayToast(data);
        }}
        // High priority: insert at front of queue
        else if (priority == ToastPriority.High && _activeToasts.Count >= maxVisible)
        {{
            // Re-create queue with high priority first
            var tempQueue = new Queue<ToastData>();
            tempQueue.Enqueue(data);
            while (_pendingQueue.Count > 0)
                tempQueue.Enqueue(_pendingQueue.Dequeue());
            _pendingQueue = tempQueue;
        }}
        else if (_activeToasts.Count < maxVisible)
        {{
            DisplayToast(data);
        }}
        else
        {{
            _pendingQueue.Enqueue(data);
        }}
    }}

    private void DisplayToast(ToastData data)
    {{
        Color accentColor = GetTypeColor(data.type);

        var toast = new VisualElement();
        toast.AddToClassList("vb-notification__toast");
        toast.style.backgroundColor = new Color(0.1f, 0.1f, 0.18f, 0.95f);
        toast.style.borderTopWidth = 2;
        toast.style.borderBottomWidth = 2;
        toast.style.borderLeftWidth = 2;
        toast.style.borderRightWidth = 2;
        toast.style.borderTopColor = accentColor;
        toast.style.borderBottomColor = new Color(0.79f, 0.66f, 0.3f, 0.4f);
        toast.style.borderLeftColor = new Color(0.79f, 0.66f, 0.3f, 0.4f);
        toast.style.borderRightColor = new Color(0.79f, 0.66f, 0.3f, 0.4f);
        toast.style.borderTopLeftRadius = 4;
        toast.style.borderTopRightRadius = 4;
        toast.style.borderBottomLeftRadius = 4;
        toast.style.borderBottomRightRadius = 4;
        toast.style.paddingTop = 8;
        toast.style.paddingBottom = 8;
        toast.style.paddingLeft = 12;
        toast.style.paddingRight = 12;
        toast.style.marginBottom = 4;
        toast.style.opacity = 0f;

        // Content row
        var contentRow = new VisualElement();
        contentRow.style.flexDirection = FlexDirection.Row;

        // Icon
        if (data.icon != null)
        {{
            var iconEl = new VisualElement();
            iconEl.style.width = 32;
            iconEl.style.height = 32;
            iconEl.style.marginRight = 8;
            iconEl.style.backgroundImage = data.icon;
            contentRow.Add(iconEl);
        }}

        // Text column
        var textColumn = new VisualElement();
        textColumn.style.flexGrow = 1;

        var titleLabel = new Label(data.title);
        titleLabel.style.color = accentColor;
        titleLabel.style.fontSize = 13;
        titleLabel.style.unityFontStyleAndWeight = FontStyle.Bold;
        textColumn.Add(titleLabel);

        if (!string.IsNullOrEmpty(data.description))
        {{
            var descLabel = new Label(data.description);
            descLabel.style.color = new Color(0.8f, 0.8f, 0.85f);
            descLabel.style.fontSize = 11;
            descLabel.style.whiteSpace = WhiteSpace.Normal;
            textColumn.Add(descLabel);
        }}

        contentRow.Add(textColumn);
        toast.Add(contentRow);
        _toastContainer.Add(toast);

        _activeToasts.Add(data);
        _activeElements.Add(toast);

        // Slide-in animation via PrimeTween
        // Tween.UIAlpha(toast, 0f, 1f, slideInDuration);
        toast.schedule.Execute(() =>
        {{
            toast.style.opacity = 1f;
        }}).StartingIn((long)(slideInDuration * 1000));
    }}

    private void DismissOldest()
    {{
        if (_activeToasts.Count == 0) return;
        DismissToast(0);
    }}

    private void DismissToast(int index)
    {{
        if (index < 0 || index >= _activeElements.Count) return;

        var element = _activeElements[index];
        element.RemoveFromHierarchy();
        _activeToasts.RemoveAt(index);
        _activeElements.RemoveAt(index);

        // Show next in queue if available
        if (_pendingQueue.Count > 0 && _activeToasts.Count < maxVisible)
            DisplayToast(_pendingQueue.Dequeue());
    }}

    private void Update()
    {{
        // Check for expired toasts
        for (int i = _activeToasts.Count - 1; i >= 0; i--)
        {{
            if (Time.time - _activeToasts[i].timestamp > _activeToasts[i].displayTime)
            {{
                DismissToast(i);
            }}
        }}
    }}

    private Color GetTypeColor(ToastType type)
    {{
        switch (type)
        {{
{type_color_switch}
            default: return new Color(0.7f, 0.7f, 0.7f);
        }}
    }}

    /// <summary>
    /// Dismiss all active notifications.
    /// </summary>
    public void DismissAll()
    {{
        for (int i = _activeElements.Count - 1; i >= 0; i--)
            DismissToast(i);
        _pendingQueue.Clear();
    }}

    /// <summary>
    /// Get the number of currently active notifications.
    /// </summary>
    public int GetActiveCount() => _activeToasts.Count;

    /// <summary>
    /// Get the number of pending notifications in the queue.
    /// </summary>
    public int GetPendingCount() => _pendingQueue.Count;
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/UI/VB_NotificationSystem.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Add VB_NotificationSystem to a UIDocument in your scene",
            "Call ShowToast(ToastType, title, description) to display notifications",
            "Configure max_visible, auto_dismiss_seconds, and position in Inspector",
        ],
    }


# ---------------------------------------------------------------------------
# UIPOL-07: Loading Screen System
# ---------------------------------------------------------------------------


def generate_loading_screen_script(
    show_tips: bool = True,
    show_lore: bool = True,
    show_art: bool = True,
    progress_style: str = "bar",
    tip_interval: float = 5.0,
) -> dict[str, Any]:
    """Generate C# + UXML/USS for loading screen system.

    Creates a loading screen with animated progress bar, random tips from
    ScriptableObject database, lore text with typewriter reveal, concept
    art display with crossfade, and dark fantasy styling.

    Args:
        show_tips: Whether to display gameplay tips.
        show_lore: Whether to display lore text with typewriter effect.
        show_art: Whether to display concept art with crossfade.
        progress_style: Progress display -- bar, circular, rune.
        tip_interval: Seconds between tip rotations.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    valid_styles = {"bar", "circular", "rune"}
    if progress_style not in valid_styles:
        progress_style = "bar"

    tip_block = ""
    if show_tips:
        tip_block = '''
    [Header("Tips")]
    [SerializeField] private string[] gameplayTips = new string[]
    {
        "Synergies between brands amplify your combat power. Experiment with combinations.",
        "Corruption grants strength but twists your abilities. Watch your threshold.",
        "Dodge at the right moment to gain i-frames and counter-attack opportunities.",
        "Explore every corner -- secret areas hold powerful lore items and gear.",
        "Each brand has unique damage types. Match them to enemy weaknesses.",
        "Equipment rarity affects both stats and visual effects on your character.",
        "Talk to NPCs after major events -- their dialogue changes with the story.",
        "The VOID brand is the rarest but most unpredictable. Use with caution.",
    };
    [SerializeField] private float tipInterval = ''' + str(tip_interval) + '''f;
    private float _nextTipTime;
    private int _currentTipIndex;

    private void UpdateTips()
    {
        if (gameplayTips == null || gameplayTips.Length == 0) return;
        if (Time.time < _nextTipTime) return;
        _nextTipTime = Time.time + tipInterval;

        _currentTipIndex = (_currentTipIndex + 1) % gameplayTips.Length;
        if (_tipLabel != null)
        {
            // Fade out, change text, fade in
            _tipLabel.style.opacity = 0f;
            _tipLabel.schedule.Execute(() =>
            {
                _tipLabel.text = gameplayTips[_currentTipIndex];
                _tipLabel.style.opacity = 1f;
            }).StartingIn(300);
        }
    }'''

    lore_block = ""
    if show_lore:
        lore_block = '''
    [Header("Lore")]
    [SerializeField] private string[] loreTexts = new string[]
    {
        "In the age before the Veil shattered, the ten brands were one unified force...",
        "The corruption seeps from the broken Veil, twisting all it touches...",
        "Those who master a brand gain its strength, but the Veil demands a price...",
    };
    [SerializeField] private float typewriterSpeed = 0.03f;
    private string _fullLoreText = "";
    private int _loreCharIndex;
    private float _nextCharTime;

    private void StartTypewriter()
    {
        if (loreTexts == null || loreTexts.Length == 0) return;
        _fullLoreText = loreTexts[Random.Range(0, loreTexts.Length)];
        _loreCharIndex = 0;
        if (_loreLabel != null) _loreLabel.text = "";
    }

    private void UpdateTypewriter()
    {
        if (string.IsNullOrEmpty(_fullLoreText) || _loreLabel == null) return;
        if (_loreCharIndex >= _fullLoreText.Length) return;
        if (Time.time < _nextCharTime) return;

        _nextCharTime = Time.time + typewriterSpeed;
        _loreCharIndex++;
        _loreLabel.text = _fullLoreText.Substring(0, _loreCharIndex);
    }'''

    art_block = ""
    if show_art:
        art_block = '''
    [Header("Concept Art")]
    [SerializeField] private Texture2D[] conceptArtImages;
    [SerializeField] private float artCrossfadeDuration = 1.5f;
    [SerializeField] private float artDisplayDuration = 8.0f;
    private int _currentArtIndex;
    private float _nextArtTime;

    private void UpdateConceptArt()
    {
        if (conceptArtImages == null || conceptArtImages.Length == 0) return;
        if (_artElement == null) return;
        if (Time.time < _nextArtTime) return;

        _nextArtTime = Time.time + artDisplayDuration;
        _currentArtIndex = (_currentArtIndex + 1) % conceptArtImages.Length;

        // Crossfade: fade out, swap image, fade in
        _artElement.style.opacity = 0f;
        _artElement.schedule.Execute(() =>
        {
            _artElement.style.backgroundImage = conceptArtImages[_currentArtIndex];
            _artElement.style.opacity = 1f;
        }).StartingIn((long)(artCrossfadeDuration * 500));
    }'''

    script = f'''// VeilBreakers Auto-Generated: Loading Screen System
// Dark fantasy loading screen with tips, lore, art, and progress bar
using UnityEngine;
using UnityEngine.UIElements;
using UnityEngine.SceneManagement;
using System.Collections;

/// <summary>
/// Loading screen system with progress bar, gameplay tips, lore text
/// with typewriter reveal, and concept art crossfade display.
/// Uses UI Toolkit and dark fantasy styling.
/// </summary>
public class VB_LoadingScreen : MonoBehaviour
{{
    [Header("Configuration")]
    [SerializeField] private UIDocument uiDocument;
    [SerializeField] private string progressStyle = "{progress_style}";
{tip_block}
{lore_block}
{art_block}

    private VisualElement _root;
    private VisualElement _loadingContainer;
    private VisualElement _progressBarFill;
    private Label _progressLabel;
    private Label _tipLabel;
    private Label _loreLabel;
    private VisualElement _artElement;
    private float _currentProgress;
    private float _targetProgress;
    private bool _isLoading;

    private void OnEnable()
    {{
        if (uiDocument == null)
            uiDocument = GetComponent<UIDocument>();
    }}

    /// <summary>
    /// Start the loading screen and begin async scene load.
    /// </summary>
    public void StartLoading(string sceneName)
    {{
        BuildLoadingScreen();
        _isLoading = true;
        _currentProgress = 0f;
        _targetProgress = 0f;
        {"StartTypewriter();" if show_lore else ""}
        StartCoroutine(LoadSceneAsync(sceneName));
    }}

    /// <summary>
    /// Show the loading screen with manual progress control.
    /// </summary>
    public void ShowManual()
    {{
        BuildLoadingScreen();
        _isLoading = true;
        _currentProgress = 0f;
        _targetProgress = 0f;
        {"StartTypewriter();" if show_lore else ""}
    }}

    /// <summary>
    /// Set the progress manually (0-1).
    /// </summary>
    public void SetProgress(float progress)
    {{
        _targetProgress = Mathf.Clamp01(progress);
    }}

    /// <summary>
    /// Hide the loading screen.
    /// </summary>
    public void Hide()
    {{
        _isLoading = false;
        if (_loadingContainer != null)
            _loadingContainer.style.display = DisplayStyle.None;
    }}

    private void BuildLoadingScreen()
    {{
        if (uiDocument == null) return;
        _root = uiDocument.rootVisualElement;
        _root.Clear();

        _loadingContainer = new VisualElement();
        _loadingContainer.AddToClassList("vb-loading");
        _loadingContainer.style.position = Position.Absolute;
        _loadingContainer.style.left = 0;
        _loadingContainer.style.top = 0;
        _loadingContainer.style.right = 0;
        _loadingContainer.style.bottom = 0;
        _loadingContainer.style.backgroundColor = new Color(0.05f, 0.05f, 0.08f, 1f);
        _loadingContainer.style.justifyContent = Justify.FlexEnd;
        _loadingContainer.style.alignItems = Align.Center;
        _loadingContainer.style.paddingBottom = 60;

        // Concept art background
        _artElement = new VisualElement();
        _artElement.AddToClassList("vb-loading__art");
        _artElement.style.position = Position.Absolute;
        _artElement.style.left = 0;
        _artElement.style.top = 0;
        _artElement.style.right = 0;
        _artElement.style.bottom = 0;
        _artElement.style.opacity = 0.3f;
        _artElement.style.backgroundSize = new BackgroundSize(BackgroundSizeType.Cover);
        _loadingContainer.Add(_artElement);

        // Dark gradient overlay
        var overlay = new VisualElement();
        overlay.style.position = Position.Absolute;
        overlay.style.left = 0;
        overlay.style.top = 0;
        overlay.style.right = 0;
        overlay.style.bottom = 0;
        overlay.style.backgroundColor = new Color(0.05f, 0.05f, 0.08f, 0.6f);
        _loadingContainer.Add(overlay);

        // Content panel at bottom
        var contentPanel = new VisualElement();
        contentPanel.style.width = Length.Percent(80);
        contentPanel.style.maxWidth = 800;
        contentPanel.style.alignItems = Align.Center;

        // Lore text
        _loreLabel = new Label();
        _loreLabel.AddToClassList("vb-loading__lore");
        _loreLabel.style.color = new Color(0.83f, 0.77f, 0.66f);
        _loreLabel.style.fontSize = 14;
        _loreLabel.style.unityFontStyleAndWeight = FontStyle.Italic;
        _loreLabel.style.whiteSpace = WhiteSpace.Normal;
        _loreLabel.style.unityTextAlign = TextAnchor.MiddleCenter;
        _loreLabel.style.marginBottom = 20;
        contentPanel.Add(_loreLabel);

        // Progress bar
        var progressBarBg = new VisualElement();
        progressBarBg.AddToClassList("vb-loading__progress-bg");
        progressBarBg.style.width = Length.Percent(100);
        progressBarBg.style.height = 6;
        progressBarBg.style.backgroundColor = new Color(0.2f, 0.2f, 0.25f);
        progressBarBg.style.borderTopLeftRadius = 3;
        progressBarBg.style.borderTopRightRadius = 3;
        progressBarBg.style.borderBottomLeftRadius = 3;
        progressBarBg.style.borderBottomRightRadius = 3;
        progressBarBg.style.borderTopWidth = 1;
        progressBarBg.style.borderBottomWidth = 1;
        progressBarBg.style.borderLeftWidth = 1;
        progressBarBg.style.borderRightWidth = 1;
        progressBarBg.style.borderTopColor = new Color(0.79f, 0.66f, 0.3f, 0.4f);
        progressBarBg.style.borderBottomColor = new Color(0.79f, 0.66f, 0.3f, 0.4f);
        progressBarBg.style.borderLeftColor = new Color(0.79f, 0.66f, 0.3f, 0.4f);
        progressBarBg.style.borderRightColor = new Color(0.79f, 0.66f, 0.3f, 0.4f);

        _progressBarFill = new VisualElement();
        _progressBarFill.AddToClassList("vb-loading__progress-fill");
        _progressBarFill.style.height = Length.Percent(100);
        _progressBarFill.style.width = Length.Percent(0);
        _progressBarFill.style.backgroundColor = new Color(0.79f, 0.66f, 0.3f);
        _progressBarFill.style.borderTopLeftRadius = 3;
        _progressBarFill.style.borderTopRightRadius = 3;
        _progressBarFill.style.borderBottomLeftRadius = 3;
        _progressBarFill.style.borderBottomRightRadius = 3;
        progressBarBg.Add(_progressBarFill);
        contentPanel.Add(progressBarBg);

        // Progress percentage
        _progressLabel = new Label("0%");
        _progressLabel.style.color = new Color(0.79f, 0.66f, 0.3f);
        _progressLabel.style.fontSize = 12;
        _progressLabel.style.marginTop = 4;
        contentPanel.Add(_progressLabel);

        // Tip text
        _tipLabel = new Label();
        _tipLabel.AddToClassList("vb-loading__tip");
        _tipLabel.style.color = new Color(0.7f, 0.7f, 0.8f);
        _tipLabel.style.fontSize = 12;
        _tipLabel.style.marginTop = 16;
        _tipLabel.style.whiteSpace = WhiteSpace.Normal;
        _tipLabel.style.unityTextAlign = TextAnchor.MiddleCenter;
        contentPanel.Add(_tipLabel);

        _loadingContainer.Add(contentPanel);
        _root.Add(_loadingContainer);
    }}

    private IEnumerator LoadSceneAsync(string sceneName)
    {{
        AsyncOperation asyncOp = SceneManager.LoadSceneAsync(sceneName);
        if (asyncOp == null)
        {{
            Debug.LogError($"[VB_LoadingScreen] Failed to load scene: {{sceneName}}");
            yield break;
        }}

        asyncOp.allowSceneActivation = false;

        while (!asyncOp.isDone)
        {{
            // Unity loads to 0.9, then waits for allowSceneActivation
            _targetProgress = asyncOp.progress < 0.9f
                ? asyncOp.progress / 0.9f
                : 1f;

            if (asyncOp.progress >= 0.9f)
            {{
                _targetProgress = 1f;
                yield return new WaitForSeconds(0.5f);
                asyncOp.allowSceneActivation = true;
            }}

            yield return null;
        }}

        _isLoading = false;
    }}

    private void Update()
    {{
        if (!_isLoading) return;

        // Smooth progress interpolation
        _currentProgress = Mathf.Lerp(_currentProgress, _targetProgress, Time.deltaTime * 5f);
        if (_progressBarFill != null)
            _progressBarFill.style.width = Length.Percent(_currentProgress * 100f);
        if (_progressLabel != null)
            _progressLabel.text = $"{{Mathf.RoundToInt(_currentProgress * 100)}}%";
        {"UpdateTips();" if show_tips else ""}
        {"UpdateTypewriter();" if show_lore else ""}
        {"UpdateConceptArt();" if show_art else ""}
    }}

    /// <summary>
    /// Check if loading is in progress.
    /// </summary>
    public bool IsLoading() => _isLoading;

    /// <summary>
    /// Get the current progress (0-1).
    /// </summary>
    public float GetProgress() => _currentProgress;
}}
'''

    return {
        "script_path": "Assets/Scripts/Runtime/UI/VB_LoadingScreen.cs",
        "script_content": script,
        "next_steps": [
            "Save the script to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Add VB_LoadingScreen to a persistent UIDocument",
            "Add scenes to Build Settings for async loading",
            "Call StartLoading(sceneName) to begin loading with screen",
            "Optionally: assign concept art textures and customize tips",
        ],
    }


# ---------------------------------------------------------------------------
# UIPOL-08: Material-Based UI Shaders
# ---------------------------------------------------------------------------


def generate_ui_material_shaders(
    shader_name: str = "VB_UIEffects",
    effects: list[str] | None = None,
) -> dict[str, Any]:
    """Generate URP ShaderLab + HLSL for material-based UI effects.

    Creates dark fantasy material shaders for UI elements:
    - Gold-leaf shine: animated specular sweep across UI
    - Blood-stain overlay: procedural noise-based blood splatter
    - Dynamic rune glow: emissive pulse synced to combat brand
    - Corruption ripple: distortion wave for corrupted UI elements

    Args:
        shader_name: Name for the shader.
        effects: List of effects to include -- gold_leaf, blood_stain,
                 rune_glow, corruption_ripple.

    Returns:
        Dict with script_path, script_content, next_steps.
    """
    if effects is None:
        effects = ["gold_leaf", "blood_stain", "rune_glow", "corruption_ripple"]

    valid_effects = {"gold_leaf", "blood_stain", "rune_glow", "corruption_ripple"}
    effects = [e for e in effects if e in valid_effects]
    if not effects:
        effects = ["gold_leaf"]

    safe_name = sanitize_cs_identifier(shader_name)

    # Build properties block
    properties_lines = [
        '        _MainTex ("Main Texture", 2D) = "white" {}',
        '        _Color ("Tint Color", Color) = (1,1,1,1)',
    ]

    if "gold_leaf" in effects:
        properties_lines.extend([
            '        [Header("Gold Leaf Shine")]',
            '        _GoldLeafEnabled ("Gold Leaf Enabled", Float) = 1',
            '        _GoldLeafSpeed ("Sweep Speed", Range(0.1, 5)) = 1.5',
            '        _GoldLeafWidth ("Sweep Width", Range(0.01, 0.3)) = 0.1',
            '        _GoldLeafIntensity ("Intensity", Range(0, 2)) = 1.0',
            '        _GoldLeafColor ("Gold Color", Color) = (0.79, 0.66, 0.3, 1)',
        ])

    if "blood_stain" in effects:
        properties_lines.extend([
            '        [Header("Blood Stain")]',
            '        _BloodEnabled ("Blood Enabled", Float) = 0',
            '        _BloodAmount ("Blood Amount", Range(0, 1)) = 0',
            '        _BloodColor ("Blood Color", Color) = (0.5, 0, 0, 1)',
            '        _BloodNoiseScale ("Noise Scale", Range(1, 20)) = 8',
            '        _BloodEdgeSoftness ("Edge Softness", Range(0, 0.5)) = 0.1',
        ])

    if "rune_glow" in effects:
        properties_lines.extend([
            '        [Header("Rune Glow")]',
            '        _RuneGlowEnabled ("Rune Glow Enabled", Float) = 0',
            '        _RuneGlowColor ("Glow Color", Color) = (0.79, 0.66, 0.3, 1)',
            '        _RuneGlowSpeed ("Pulse Speed", Range(0.1, 5)) = 2.0',
            '        _RuneGlowIntensity ("Glow Intensity", Range(0, 3)) = 1.5',
            '        _RuneMask ("Rune Mask", 2D) = "black" {}',
        ])

    if "corruption_ripple" in effects:
        properties_lines.extend([
            '        [Header("Corruption Ripple")]',
            '        _CorruptionEnabled ("Corruption Enabled", Float) = 0',
            '        _CorruptionAmount ("Corruption Amount", Range(0, 1)) = 0',
            '        _CorruptionSpeed ("Ripple Speed", Range(0.1, 5)) = 1.0',
            '        _CorruptionFrequency ("Ripple Frequency", Range(1, 20)) = 8',
            '        _CorruptionDistortion ("Distortion Strength", Range(0, 0.1)) = 0.02',
            '        _CorruptionColor ("Corruption Color", Color) = (0.24, 0.06, 0.06, 1)',
        ])

    properties_str = "\n".join(properties_lines)

    # Build HLSL variable declarations
    hlsl_vars = [
        "            sampler2D _MainTex;",
        "            float4 _MainTex_ST;",
        "            float4 _Color;",
    ]

    if "gold_leaf" in effects:
        hlsl_vars.extend([
            "            float _GoldLeafEnabled;",
            "            float _GoldLeafSpeed;",
            "            float _GoldLeafWidth;",
            "            float _GoldLeafIntensity;",
            "            float4 _GoldLeafColor;",
        ])
    if "blood_stain" in effects:
        hlsl_vars.extend([
            "            float _BloodEnabled;",
            "            float _BloodAmount;",
            "            float4 _BloodColor;",
            "            float _BloodNoiseScale;",
            "            float _BloodEdgeSoftness;",
        ])
    if "rune_glow" in effects:
        hlsl_vars.extend([
            "            float _RuneGlowEnabled;",
            "            float4 _RuneGlowColor;",
            "            float _RuneGlowSpeed;",
            "            float _RuneGlowIntensity;",
            "            sampler2D _RuneMask;",
        ])
    if "corruption_ripple" in effects:
        hlsl_vars.extend([
            "            float _CorruptionEnabled;",
            "            float _CorruptionAmount;",
            "            float _CorruptionSpeed;",
            "            float _CorruptionFrequency;",
            "            float _CorruptionDistortion;",
            "            float4 _CorruptionColor;",
        ])

    # Wrap in CBUFFER for SRP Batcher compatibility
    cbuffer_vars = [v for v in hlsl_vars if "sampler2D" not in v]
    texture_vars = [v for v in hlsl_vars if "sampler2D" in v]
    hlsl_parts = []
    hlsl_parts.extend(texture_vars)
    hlsl_parts.append("            CBUFFER_START(UnityPerMaterial)")
    hlsl_parts.extend(cbuffer_vars)
    hlsl_parts.append("            CBUFFER_END")
    hlsl_vars_str = "\n".join(hlsl_parts)

    # Build fragment shader effect blocks
    frag_effects = []

    if "corruption_ripple" in effects:
        frag_effects.append('''
                // Corruption ripple distortion (applied before texture sampling)
                if (_CorruptionEnabled > 0.5)
                {
                    float ripple = sin(i.uv.x * _CorruptionFrequency + _Time.y * _CorruptionSpeed)
                                 * sin(i.uv.y * _CorruptionFrequency + _Time.y * _CorruptionSpeed * 0.7);
                    float distortionMask = _CorruptionAmount;
                    uv += float2(ripple, ripple) * _CorruptionDistortion * distortionMask;
                }''')

    frag_effects.append('''
                // Sample main texture
                float4 col = tex2D(_MainTex, uv) * _Color;''')

    if "gold_leaf" in effects:
        frag_effects.append('''
                // Gold leaf animated shine sweep
                if (_GoldLeafEnabled > 0.5)
                {
                    float sweepPos = frac(_Time.y * _GoldLeafSpeed * 0.2);
                    float dist = abs(i.uv.x + i.uv.y - sweepPos * 3.0);
                    float shine = saturate(1.0 - dist / _GoldLeafWidth);
                    shine = shine * shine * _GoldLeafIntensity;
                    col.rgb += _GoldLeafColor.rgb * shine * col.a;
                }''')

    if "blood_stain" in effects:
        frag_effects.append('''
                // Blood stain overlay with procedural noise
                if (_BloodEnabled > 0.5 && _BloodAmount > 0.01)
                {
                    float2 noiseUV = i.uv * _BloodNoiseScale;
                    // Simple hash-based noise
                    float noise = frac(sin(dot(noiseUV, float2(12.9898, 78.233))) * 43758.5453);
                    float noise2 = frac(sin(dot(noiseUV * 1.5 + 0.5, float2(39.346, 11.135))) * 65421.321);
                    float combined = (noise + noise2) * 0.5;

                    // Threshold based on blood amount
                    float threshold = 1.0 - _BloodAmount;
                    float bloodMask = smoothstep(threshold - _BloodEdgeSoftness,
                                                  threshold + _BloodEdgeSoftness, combined);
                    col.rgb = lerp(col.rgb, _BloodColor.rgb, bloodMask * _BloodColor.a);
                }''')

    if "rune_glow" in effects:
        frag_effects.append('''
                // Dynamic rune glow with pulsing emissive
                if (_RuneGlowEnabled > 0.5)
                {
                    float runeMask = tex2D(_RuneMask, i.uv).r;
                    float pulse = (sin(_Time.y * _RuneGlowSpeed) + 1.0) * 0.5;
                    float glow = runeMask * pulse * _RuneGlowIntensity;
                    col.rgb += _RuneGlowColor.rgb * glow;
                }''')

    if "corruption_ripple" in effects:
        frag_effects.append('''
                // Corruption color tint
                if (_CorruptionEnabled > 0.5)
                {
                    float corruptionVignette = length(i.uv - 0.5) * 2.0;
                    float corruptionMask = saturate(corruptionVignette * _CorruptionAmount);
                    col.rgb = lerp(col.rgb, _CorruptionColor.rgb, corruptionMask * 0.5);
                }''')

    frag_effects_str = "\n".join(frag_effects)

    shader_code = f'''// VeilBreakers Auto-Generated: Material-Based UI Shaders
// Dark fantasy UI effects: {", ".join(effects)}
Shader "VeilBreakers/UI/{safe_name}"
{{
    Properties
    {{
{properties_str}
    }}

    SubShader
    {{
        Tags
        {{
            "RenderType" = "Transparent"
            "Queue" = "Transparent"
            "RenderPipeline" = "UniversalPipeline"
        }}

        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        Pass
        {{
            Name "VB_UIEffects"

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_instancing

            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

{hlsl_vars_str}

            struct Attributes
            {{
                float4 positionOS : POSITION;
                float2 uv : TEXCOORD0;
                float4 color : COLOR;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            }};

            struct Varyings
            {{
                float4 positionCS : SV_POSITION;
                float2 uv : TEXCOORD0;
                float4 color : COLOR;
                UNITY_VERTEX_OUTPUT_STEREO
            }};

            Varyings vert(Attributes v)
            {{
                Varyings o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.positionCS = TransformObjectToHClip(v.positionOS.xyz);
                o.uv = TRANSFORM_TEX(v.uv, _MainTex);
                o.color = v.color;
                return o;
            }}

            float4 frag(Varyings i) : SV_Target
            {{
                float2 uv = i.uv;
{frag_effects_str}

                col *= i.color;
                return col;
            }}
            ENDHLSL
        }}
    }}

    Fallback "UI/Default"
}}
'''

    return {
        "script_path": f"Assets/Shaders/UI/{safe_name}.shader",
        "script_content": shader_code,
        "effects_included": effects,
        "next_steps": [
            "Save the shader file to your Unity project",
            "Call unity_editor action=recompile to compile",
            "Create a Material using VeilBreakers/UI/" + safe_name,
            "Assign to UI Image or custom UI element",
            "Enable effects via material properties in Inspector",
            "Animate _BloodAmount / _CorruptionAmount at runtime for dynamic effects",
        ],
    }
