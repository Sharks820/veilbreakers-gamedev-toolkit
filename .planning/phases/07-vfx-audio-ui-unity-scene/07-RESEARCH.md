# Phase 7: VFX, Audio, UI & Unity Scene - Research

**Researched:** 2026-03-19
**Domain:** Unity-side tooling via MCP -- VFX Graph particle templates, AI audio generation (ElevenLabs), UI Toolkit (UXML/USS), scene setup (terrain/lighting/NavMesh/animator), auto-recompile/play mode, and visual quality review
**Confidence:** HIGH

## Summary

This phase is architecturally distinct from all previous phases. Phases 1-6 built Blender addon handlers dispatched through a Python MCP server via TCP socket. Phase 7 delivers Unity-side tools that generate C# scripts, UXML/USS files, shader code, and audio assets -- then use the existing `mcp-unity` package (CoderGamester, installed via Unity Package Manager) to execute operations in the Unity Editor. The Python MCP toolkit generates file content and writes it to the Unity project directory; mcp-unity's `recompile_scripts` tool triggers Unity to pick up new scripts, and `execute_menu_item` can invoke custom editor commands.

The phase splits into five functional domains: (1) VFX system -- VFX Graph cannot be created programmatically via API, so the approach is C# editor scripts that instantiate prefab templates and configure exposed properties via `VisualEffect.SetFloat/SetVector4/SetGradient`; Shader Graph similarly lacks a public creation API, so shaders are generated as raw HLSL `.shader` files with string templates. (2) Audio system -- ElevenLabs Python SDK v2.39.0 provides `text_to_sound_effects.convert()` for SFX and `text_to_speech.convert()` for voice lines; music loops use the SFX endpoint with looping enabled. (3) UI system -- UXML and USS files are generated as text templates by Python, then loaded in Unity via `VisualTreeAsset.Instantiate()`. (4) Scene setup -- C# editor scripts use `TerrainData.SetHeights()`, `NavMeshSurface.BuildNavMesh()`, `AnimatorController.CreateAnimatorControllerAtPath()`, and Volume profile APIs. (5) Unity auto-recompile -- leverages mcp-unity's built-in `recompile_scripts` tool plus custom editor scripts for `EditorApplication.EnterPlaymode()`, `ScreenCapture.CaptureScreenshot()`, and console log retrieval.

The toolkit needs 4-5 new compound MCP tools (`unity_vfx`, `unity_audio`, `unity_ui`, `unity_scene`, `unity_editor`) with Python-side template generators and optional ElevenLabs API integration. Unlike Blender handlers that run inside Blender's Python, Unity tools generate C# source files that mcp-unity compiles and executes. This is a "code generation" pattern, not a "remote procedure call" pattern.

**Primary recommendation:** Build Python-side template generators that emit C# editor scripts, UXML/USS, and HLSL shader files into the Unity project. Use mcp-unity for compilation triggering, scene manipulation, and play mode control. ElevenLabs SDK handles all AI audio generation server-side in Python. Target 5-6 plans covering: (1) Unity bridge + auto-recompile, (2) VFX templates + shaders, (3) audio generation, (4) UI generation, (5) scene setup, (6) visual review.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- VFX descriptions are parsed into VFX Graph component parameters (rate, lifetime, size, color, shape)
- Per-brand VFX variants: IRON (sparks, metal), VENOM (drip, acid green), SURGE (crackle, electric blue)
- Corruption shader scales visual corruption percentage on materials
- Environmental VFX: dust, fireflies, snow, rain, ash as reusable prefab templates
- Shader Graph templates: dissolve, force field, water, foliage, outline
- AI SFX generation via ElevenLabs or stub (sound description -> wav file)
- Music loop generation: combat, exploration, boss, town themes
- Voice line synthesis for NPCs/monsters
- Ambient soundscape per biome (forest, cave, town, dungeon)
- Footstep system maps surface material to sound bank
- Adaptive music layers add/remove tracks based on game state
- Unity Audio Mixer setup with group routing and audio pool manager
- UI screens generated from text descriptions as UXML + USS (Unity UI Toolkit)
- Layout validation: overlap detection, zero-size elements, overflow, WCAG contrast
- Responsive testing at 5 standard resolutions (1920x1080, 2560x1440, 3840x2160, 1280x720, 800x600)
- Post-processing: bloom, color grading, vignette, AO, DOF
- Screen effects: camera shake, damage vignette, heal glow, poison overlay
- Scene import: terrain heightmaps, object scatter, lighting/fog/post-processing
- NavMesh baking with configurable agent settings
- Animator Controller setup with blend trees
- Screenshot comparison for visual regression detection
- Tool to trigger AssetDatabase.Refresh() for script recompilation
- Enter/exit play mode programmatically
- Capture screenshots of game/scene view
- Read Unity console logs for errors/warnings

### Claude's Discretion
All implementation choices are at Claude's discretion -- autonomous execution mode.

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VFX-01 | VFX Graph particle system from text description | C# template generates VFX prefab with VisualEffect component; exposed properties (rate, lifetime, size, color, shape) set via SetFloat/SetVector4; text parsing maps keywords to parameter presets |
| VFX-02 | Per-brand damage VFX (IRON sparks, VENOM drip, SURGE crackle) | Brand config dicts map to VFX parameter sets; C# ScriptableObject stores brand VFX profiles; prefab variants per brand |
| VFX-03 | Environmental VFX (dust motes, fireflies, snow, rain, ash) | Reusable VFX prefab templates with configurable parameters; C# editor script instantiates and configures from JSON spec |
| VFX-04 | Weapon/projectile trail effects with fade | C# TrailRenderer or VFX Graph trail system; template with width curve, color gradient, lifetime params |
| VFX-05 | Character aura/buff VFX (corruption glow, healing shimmer) | Particle system templates with looping, world-space emission around character bounds |
| VFX-06 | Corruption shader scaling (0-100%) | HLSL .shader template with _CorruptionAmount float property; lerps between clean and corrupted material properties |
| VFX-07 | Shader Graph creation (dissolve, force field, water, foliage, outline, damage overlay) | Generate as .shader HLSL files (no Shader Graph API); string templates with configurable parameters |
| VFX-08 | Post-processing setup (bloom, color grading, vignette, AO, DOF) | C# editor script creates Volume GameObject with VolumeProfile; adds overrides via profile.Add<Bloom>() etc. |
| VFX-09 | Screen effects (camera shake, damage vignette, low health pulse) | Camera shake via Cinemachine Impulse GenerateImpulse(); overlay effects via fullscreen shader + CanvasGroup alpha |
| VFX-10 | Hero/monster ability VFX with animation integration | Combines VFX prefab instantiation with AnimationEvent binding at specified keyframes |
| AUD-01 | AI SFX generation from text description | ElevenLabs Python SDK text_to_sound_effects.convert(text=description, duration_seconds=N); saves .wav to Unity Assets/Audio/SFX/ |
| AUD-02 | Music loop generation (combat, exploration, boss, town) | ElevenLabs SFX endpoint with loop=True, duration_seconds=22-30; genre keywords in prompt for style control |
| AUD-03 | Voice line synthesis for NPCs/monsters | ElevenLabs text_to_speech.convert(text=dialogue, voice_id=id); voice cloning or preset voices for character types |
| AUD-04 | Ambient soundscape per biome | Layer multiple ElevenLabs SFX calls (wind + birds + water); Python mixer combines layers or generates as separate AudioClips |
| AUD-05 | Surface-material footstep system | Python generates C# FootstepManager script + ScriptableObject sound banks per surface type; audio files from ElevenLabs or stub |
| AUD-06 | Adaptive music layers | C# AudioManager with layered AudioSources; Python generates the manager script + layer configuration ScriptableObject |
| AUD-07 | Audio zones (reverb for caves, outdoor, indoor) | C# editor script creates AudioReverbZone GameObjects with preset configs per zone type |
| AUD-08 | Unity Audio Mixer with groups | AudioMixer asset created via C# editor script using internal API or template .mixer file; groups: SFX, Music, Voice, Ambient, UI |
| AUD-09 | Audio manager with pooling, priority, ducking | C# template for AudioPoolManager MonoBehaviour with configurable pool size, priority system, ducking rules |
| AUD-10 | Assign SFX to animation events | C# editor script adds AnimationEvent at specified frames via AnimationUtility.SetAnimationEvents() |
| UI-01 | Game view screenshot capture | mcp-unity's existing tools + custom C# editor script using ScreenCapture.CaptureScreenshot() at specified resolution |
| UI-02 | UI layout validation | Python parses UXML tree structure; checks for overlaps (bounding box intersection), zero-size, overflow, contrast ratios |
| UI-03 | Responsive testing at 5 resolutions | C# editor script sets GameView resolution, captures screenshot at each; Python compares layouts |
| UI-04 | Gemini visual review integration | Python sends screenshot to Gemini API (or similar) with quality assessment prompt; returns structured feedback |
| UI-05 | UI screen generation (UXML + USS) | Python template engine maps text description to UXML element hierarchy + USS stylesheet; dark fantasy theme defaults |
| UI-06 | WCAG contrast ratio validation | Python implements W3C relative luminance formula: L = 0.2126*R + 0.7152*G + 0.0722*B; ratio = (L1+0.05)/(L2+0.05); threshold 4.5:1 for AA |
| UI-07 | Screenshot comparison for visual regression | Python PIL/OpenCV pixel diff between reference and current screenshots; threshold for acceptable change percentage |
| SCENE-01 | Unity Terrain from heightmap with splatmaps | C# editor script creates TerrainData, calls SetHeights() from imported RAW heightmap, SetAlphamaps() for splatmaps |
| SCENE-02 | Object scattering with density rules | C# editor script instantiates prefabs with Poisson disk or grid sampling; density filtered by terrain slope/altitude |
| SCENE-03 | Lighting setup (directional, ambient, fog, post-processing) | C# editor script configures RenderSettings (ambientLight, fog, skybox) + creates directional light + Volume profile |
| SCENE-04 | NavMesh baking with agent settings | C# editor script uses NavMeshSurface.BuildNavMesh() with configured agent radius/height/slope; adds NavMeshLinks |
| SCENE-05 | Animator Controller creation | AnimatorController.CreateAnimatorControllerAtPath(); AddParameter(); stateMachine.AddState(); AddTransition() with conditions |
| SCENE-06 | Avatar configuration (Humanoid/Generic) | C# editor script sets ModelImporter.animationType and calls ModelImporter.SaveAndReimport(); configures bone mapping |
| SCENE-07 | Animation Rigging constraints (Two-Bone IK, Multi-Aim) | C# adds TwoBoneIKConstraint/MultiAimConstraint components via AddComponent<T>(); configures source/target transforms |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| elevenlabs (Python SDK) | 2.39.0 | AI SFX generation, voice synthesis, music loops | Official SDK; text_to_sound_effects.convert() and text_to_speech.convert() endpoints |
| mcp-unity (Unity package) | 1.2.0+ | Unity Editor MCP bridge -- recompile, menu items, scene manipulation | Already referenced in project .mcp.json; 25 tools for editor automation |
| Pillow | >=12.1.0 | Screenshot comparison, image diff, WCAG color extraction | Already in project dependencies |
| mcp[cli] | >=1.26.0 | FastMCP server framework | Already in project dependencies |
| pydantic-settings | >=2.0 | Settings/config management including ElevenLabs API key | Already in project dependencies |

### Supporting (Unity-side, installed via mcp-unity)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| com.unity.visualeffectgraph | 14.x+ | VFX Graph runtime for particle effects | VFX-01 through VFX-05, VFX-10 |
| com.unity.cinemachine | 3.x | Camera shake via Impulse system | VFX-09 screen effects |
| com.unity.render-pipelines.universal (URP) | 14.x+ | Post-processing Volume, bloom, color grading | VFX-08, SCENE-03 |
| com.unity.animation.rigging | 1.3.x | TwoBoneIKConstraint, MultiAimConstraint | SCENE-07 |
| com.unity.ai.navigation | 2.x | NavMeshSurface runtime baking | SCENE-04 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ElevenLabs SFX | Stability AI audio | ElevenLabs has dedicated SFX v2 endpoint with loop support; Stability's audio model less mature |
| ElevenLabs TTS | Azure Cognitive TTS | ElevenLabs has better voice quality for game characters; single SDK for both SFX and TTS |
| Raw HLSL shaders | Shader Graph JSON manipulation | Shader Graph has no public API; JSON format is undocumented/unstable; raw HLSL is reliable and fully controllable |
| mcp-unity | Custom Unity WebSocket bridge | mcp-unity already installed and provides 25 tools; no need to reinvent |
| Pillow for image diff | OpenCV | Pillow already in deps; sufficient for pixel-level comparison; OpenCV adds heavy dependency |

### New Dependencies
```bash
# Add to pyproject.toml [project] dependencies:
# elevenlabs>=2.39.0

# In Unity Package Manager (via mcp-unity or manual):
# com.unity.visualeffectgraph (if not already installed)
# com.unity.cinemachine
# com.unity.animation.rigging
# com.unity.ai.navigation
```

## Architecture Patterns

### Critical: Code Generation Pattern (NOT Remote Procedure Call)

Phase 7 uses a fundamentally different architecture from Phases 1-6:

**Phases 1-6 (Blender):** Python MCP server -> TCP socket -> Blender addon -> handler executes bpy/bmesh code
**Phase 7 (Unity):** Python MCP server -> generates C# files/UXML/USS/HLSL -> writes to Unity project -> mcp-unity triggers recompile -> mcp-unity executes editor commands

The Python MCP toolkit acts as a **code generator**, not a **remote executor**. It:
1. Builds C# scripts from string templates
2. Writes them to the Unity project's `Assets/Editor/Generated/` directory
3. Calls mcp-unity's `recompile_scripts` to trigger compilation
4. Calls mcp-unity's `execute_menu_item` to run the generated editor commands
5. Reads results via mcp-unity's `get_console_logs` or file output

### Recommended Project Structure (Unity side)
```
Assets/
  Editor/
    Generated/
      VFX/           # VFX editor scripts (create prefabs, configure effects)
      Audio/          # Audio setup scripts (mixer, manager, zone configs)
      UI/             # UI generation scripts
      Scene/          # Scene setup scripts (terrain, lighting, NavMesh)
      AutoRecompile/  # Editor utility scripts (refresh, play mode, screenshot)
  Scripts/
    Runtime/
      VFX/            # Runtime VFX controllers (corruption shader, screen effects)
      Audio/          # AudioPoolManager, FootstepManager, AdaptiveMusicManager
      UI/             # UI screen controllers, responsive layout managers
  Resources/
    VFX/              # VFX Graph assets, shader includes
    Audio/            # Generated .wav/.mp3 files
    UI/               # UXML + USS templates
  Prefabs/
    VFX/              # VFX prefab templates
    Audio/            # Audio zone prefabs
```

### Recommended Project Structure (Python MCP side)
```
Tools/mcp-toolkit/
  src/veilbreakers_mcp/
    unity_server.py          # New FastMCP server for Unity tools
    shared/
      elevenlabs_client.py   # ElevenLabs API wrapper (SFX + TTS)
      unity_templates/       # C# template strings
        vfx_templates.py     # VFX Graph config, shader HLSL templates
        audio_templates.py   # AudioManager, FootstepManager C# templates
        ui_templates.py      # UXML/USS generation from descriptions
        scene_templates.py   # Terrain, lighting, NavMesh C# templates
        editor_templates.py  # Auto-recompile, play mode, screenshot C# templates
      wcag_checker.py        # WCAG contrast ratio calculation
      screenshot_diff.py     # Visual regression image comparison
```

### Pattern 1: C# Template Generation
**What:** Python generates C# editor scripts from parameterized templates, writes to Unity project, triggers compilation
**When to use:** All Unity-side asset creation (VFX, audio setup, scene config)
**Example:**
```python
# Source: Established project pattern (string template + file write)
def generate_vfx_setup_script(params: dict) -> str:
    """Generate C# editor script that creates a VFX prefab."""
    return f"""
using UnityEngine;
using UnityEditor;
using UnityEngine.VFX;

public static class VFXSetup_{params['name']}
{{
    [MenuItem("VeilBreakers/VFX/Create {params['name']}")]
    public static void Create()
    {{
        var go = new GameObject("{params['name']}_VFX");
        var vfx = go.AddComponent<VisualEffect>();
        vfx.visualEffectAsset = AssetDatabase.LoadAssetAtPath<VisualEffectAsset>(
            "{params['vfx_asset_path']}");
        vfx.SetFloat("Rate", {params['rate']}f);
        vfx.SetFloat("Lifetime", {params['lifetime']}f);
        vfx.SetFloat("Size", {params['size']}f);
        vfx.SetVector4("Color", new Vector4(
            {params['color'][0]}f, {params['color'][1]}f,
            {params['color'][2]}f, {params['color'][3]}f));

        var prefabPath = "Assets/Prefabs/VFX/{params['name']}.prefab";
        PrefabUtility.SaveAsPrefabAsset(go, prefabPath);
        DestroyImmediate(go);
        AssetDatabase.Refresh();
        Debug.Log("[VeilBreakers] Created VFX prefab: " + prefabPath);
    }}
}}
"""
```

### Pattern 2: ElevenLabs Audio Generation
**What:** Python calls ElevenLabs API, receives audio bytes, writes .wav/.mp3 to Unity Assets directory
**When to use:** SFX generation (AUD-01), music loops (AUD-02), voice lines (AUD-03), ambient sounds (AUD-04)
**Example:**
```python
# Source: ElevenLabs official docs (https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert)
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key=settings.elevenlabs_api_key)

# SFX generation
audio_iter = client.text_to_sound_effects.convert(
    text="sword slash metal impact with sparks",
    duration_seconds=2.0,
    prompt_influence=0.5,
)
audio_bytes = b"".join(audio_iter)
output_path = unity_project / "Assets/Resources/Audio/SFX/sword_slash.mp3"
output_path.write_bytes(audio_bytes)

# Voice line synthesis
audio_iter = client.text_to_speech.convert(
    text="You dare enter my domain?",
    voice_id="monster_voice_id",
    model_id="eleven_multilingual_v2",
)
```

### Pattern 3: UXML/USS Template Generation
**What:** Python maps text descriptions to UXML element hierarchy + USS stylesheet
**When to use:** UI screen generation (UI-05)
**Example:**
```python
# Source: Unity docs (https://docs.unity3d.com/Manual/UIE-UXML.html)
def generate_uxml(screen_spec: dict) -> str:
    """Generate UXML from screen specification."""
    elements = []
    for elem in screen_spec["elements"]:
        if elem["type"] == "label":
            elements.append(
                f'  <ui:Label text="{elem["text"]}" '
                f'class="{elem.get("class", "default-label")}" />'
            )
        elif elem["type"] == "button":
            elements.append(
                f'  <ui:Button text="{elem["text"]}" '
                f'name="{elem["name"]}" class="vb-button" />'
            )
    body = "\n".join(elements)
    return f"""<ui:UXML xmlns:ui="UnityEngine.UIElements">
  <ui:VisualElement class="screen-root">
{body}
  </ui:VisualElement>
</ui:UXML>"""
```

### Pattern 4: mcp-unity Integration Flow
**What:** Python writes files, then uses mcp-unity tools to compile and execute
**When to use:** Any operation that needs Unity to process generated files
**Flow:**
1. Python generates C#/UXML/USS/HLSL file content
2. Python writes files to Unity project directory (using filesystem, not mcp-unity)
3. Python calls mcp-unity `recompile_scripts` tool to trigger AssetDatabase.Refresh()
4. Python calls mcp-unity `execute_menu_item` with the generated MenuItem path
5. Python calls mcp-unity `get_console_logs` to verify success/capture errors

### Anti-Patterns to Avoid
- **Trying to create VFX Graph or Shader Graph programmatically:** Neither has a public creation API. VFX Graph can only be controlled via exposed properties on existing assets. Shader Graph has no API at all. Generate raw HLSL `.shader` files instead.
- **Creating AudioMixer at runtime:** AudioMixer hierarchy must be created in Editor. Generate a C# editor script that creates the mixer asset using internal/reflection APIs, or ship a template .mixer asset.
- **Using mcp-unity for file writing:** mcp-unity tools are for Unity Editor operations. Use Python filesystem I/O to write files directly to the Unity project directory (faster, no serialization overhead).
- **Embedding Unity API calls in Python:** Python cannot call Unity C# APIs directly. All Unity operations must go through generated C# scripts executed via mcp-unity.
- **Forgetting domain reload:** When mcp-unity's `recompile_scripts` triggers a domain reload, the WebSocket connection drops temporarily. The Python side must handle reconnection/retry.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AI sound effect generation | Custom audio synthesis | ElevenLabs text_to_sound_effects v2 | Professional quality, looping support, 48kHz, royalty-free |
| AI voice synthesis | Custom TTS | ElevenLabs text_to_speech | 30+ languages, emotional awareness, character voices |
| Unity Editor bridge | Custom WebSocket server | mcp-unity (CoderGamester) | 25 tools, active maintenance, handles domain reload, WebSocket reconnection |
| WCAG contrast calculation | Approximate color comparison | W3C relative luminance formula | Industry standard: L = 0.2126*sR + 0.7152*sG + 0.0722*sB with gamma correction |
| Camera shake | Custom transform oscillation | Cinemachine Impulse system | Built-in Unity package, 6DOF shake, distance attenuation, professional quality |
| NavMesh baking | Custom pathfinding | NavMeshSurface.BuildNavMesh() | Unity's native system, handles all edge cases, configurable agent settings |
| Animator state machines | Custom FSM | AnimatorController API | Full editor integration, blend trees, transitions, parameters -- all scriptable |
| Image comparison | Pixel-by-pixel loop | Pillow ImageChops.difference() | Optimized C implementation, handles format conversion, alpha channel support |

**Key insight:** Phase 7 is about orchestrating existing Unity systems via code generation, not implementing game systems from scratch. Every C# script generated should use Unity's built-in APIs (VFX Graph, Audio Mixer, UI Toolkit, NavMesh, Animation Rigging) rather than custom implementations.

## Common Pitfalls

### Pitfall 1: Domain Reload Drops mcp-unity Connection
**What goes wrong:** Calling `recompile_scripts` triggers Unity domain reload, which stops the mcp-unity WebSocket server. Subsequent tool calls fail with connection errors.
**Why it happens:** Unity reloads all C# assemblies when scripts change, which destroys all Editor state including WebSocket connections.
**How to avoid:** After calling `recompile_scripts`, wait for Unity to finish compilation (poll `get_console_logs` for "Assembly Reload" completion), then retry the next operation. Add a configurable delay (2-5 seconds) as safety margin.
**Warning signs:** ConnectionRefused or timeout errors after any recompile operation.

### Pitfall 2: VFX Graph Has No Creation API
**What goes wrong:** Attempting to programmatically create VFX Graph nodes, connections, or systems fails because no public API exists.
**Why it happens:** VFX Graph is a visual editor tool; its internal representation is not exposed for scripting.
**How to avoid:** Use a prefab-template approach: ship base VFX Graph assets in the project, then configure exposed properties (rate, lifetime, size, color, shape) via the VisualEffect C# component API (SetFloat, SetVector4, SetGradient, SetTexture).
**Warning signs:** Looking for classes like `VFXGraph`, `VFXNode`, `VFXBlock` in editor namespace -- these exist but are internal/undocumented.

### Pitfall 3: Shader Graph Has No Public API Either
**What goes wrong:** Attempting to create Shader Graph .shadergraph files programmatically by manipulating JSON fails on format changes between versions.
**Why it happens:** .shadergraph files use an internal JSON format that changes between Unity versions with no backwards-compatibility guarantee.
**How to avoid:** Generate raw HLSL `.shader` files using ShaderLab syntax. For the required effects (dissolve, force field, water, foliage, outline), HLSL templates are more reliable and version-independent than Shader Graph manipulation.
**Warning signs:** Parsing .shadergraph JSON, importing UnityEditor.ShaderGraph namespace.

### Pitfall 4: AudioMixer Cannot Be Created Programmatically
**What goes wrong:** No public C# API exists to create AudioMixer groups or routing at editor time.
**Why it happens:** Unity's AudioMixer is an editor-only asset with no scriptable creation API (only FindMatchingGroups/SetFloat for existing mixers).
**How to avoid:** Two options: (a) Ship a pre-configured .mixer template asset and copy it into the project, or (b) use Unity's internal API via reflection (SerializedObject on AudioMixerController) -- fragile but possible. Recommend option (a) with a binary .mixer template embedded in the toolkit.
**Warning signs:** Searching for `AudioMixer.Create()` or `new AudioMixerGroup()` -- these don't exist.

### Pitfall 5: ScreenCapture Only Works in Play Mode
**What goes wrong:** `ScreenCapture.CaptureScreenshot()` silently fails when called from Edit mode because it requires the Game view to be active and playing.
**Why it happens:** Unity's screen capture API captures the rendered game frame, which only exists during Play mode.
**How to avoid:** Use `EditorApplication.EnterPlaymode()` first, wait for play mode to start (check `EditorApplication.isPlaying`), then capture. For Edit mode screenshots, use `UnityEditorInternal.InternalEditorUtility.RepaintAllViews()` combined with `EditorGUIUtility.RenderGameViewCameras()` or the Unity Recorder package.
**Warning signs:** Empty or missing screenshot files after capture in Edit mode.

### Pitfall 6: ElevenLabs Rate Limits
**What goes wrong:** Batch audio generation (e.g., generating 50 footstep variants) hits API rate limits and fails mid-batch.
**Why it happens:** ElevenLabs has per-minute rate limits that vary by subscription tier.
**How to avoid:** Implement retry logic with exponential backoff in the ElevenLabs client wrapper. Process audio generation sequentially with configurable delay between calls. Support stub mode (return silence/placeholder) for development without API access.
**Warning signs:** HTTP 429 responses from ElevenLabs API.

### Pitfall 7: Unity Project Path Must Be Known
**What goes wrong:** Python generates files but writes them to the wrong directory because Unity project path isn't configured.
**Why it happens:** The Python MCP toolkit doesn't inherently know where the Unity project lives on disk.
**How to avoid:** Add `unity_project_path` to Settings (pydantic-settings) with env var `UNITY_PROJECT_PATH`. Validate path exists and contains `Assets/` directory on startup.
**Warning signs:** FileNotFoundError when writing generated C# scripts.

## Code Examples

### Unity Auto-Recompile Editor Script (C# template)
```csharp
// Source: Unity docs (EditorApplication.EnterPlaymode, AssetDatabase.Refresh)
// Generated by Python, placed in Assets/Editor/Generated/AutoRecompile/
using UnityEngine;
using UnityEditor;

public static class VeilBreakersEditorUtils
{
    [MenuItem("VeilBreakers/Editor/Force Recompile")]
    public static void ForceRecompile()
    {
        AssetDatabase.Refresh(ImportAssetOptions.ForceUpdate);
        Debug.Log("[VeilBreakers] Forced recompile complete.");
    }

    [MenuItem("VeilBreakers/Editor/Enter Play Mode")]
    public static void EnterPlayMode()
    {
        if (!EditorApplication.isPlaying)
        {
            EditorApplication.EnterPlaymode();
            Debug.Log("[VeilBreakers] Entering play mode.");
        }
    }

    [MenuItem("VeilBreakers/Editor/Exit Play Mode")]
    public static void ExitPlayMode()
    {
        if (EditorApplication.isPlaying)
        {
            EditorApplication.ExitPlaymode();
            Debug.Log("[VeilBreakers] Exiting play mode.");
        }
    }

    [MenuItem("VeilBreakers/Editor/Capture Screenshot")]
    public static void CaptureScreenshot()
    {
        var path = "Screenshots/vb_capture_" +
            System.DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".png";
        ScreenCapture.CaptureScreenshot(path, 1);
        Debug.Log("[VeilBreakers] Screenshot saved: " + path);
    }
}
```

### HLSL Dissolve Shader Template
```hlsl
// Source: Standard Unity ShaderLab dissolve pattern
// Generated by Python vfx_templates.py
Shader "VeilBreakers/Dissolve"
{
    Properties
    {
        _MainTex ("Albedo", 2D) = "white" {}
        _NoiseTex ("Dissolve Noise", 2D) = "white" {}
        _DissolveAmount ("Dissolve Amount", Range(0, 1)) = 0
        _EdgeWidth ("Edge Width", Range(0, 0.1)) = 0.02
        _EdgeColor ("Edge Color", Color) = (1, 0.5, 0, 1)
    }
    SubShader
    {
        Tags { "RenderType"="TransparentCutout" "Queue"="AlphaTest" }

        Pass
        {
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct Attributes { float4 posOS : POSITION; float2 uv : TEXCOORD0; };
            struct Varyings { float4 posCS : SV_POSITION; float2 uv : TEXCOORD0; };

            TEXTURE2D(_MainTex); SAMPLER(sampler_MainTex);
            TEXTURE2D(_NoiseTex); SAMPLER(sampler_NoiseTex);
            float _DissolveAmount;
            float _EdgeWidth;
            float4 _EdgeColor;

            Varyings vert(Attributes IN)
            {
                Varyings OUT;
                OUT.posCS = TransformObjectToHClip(IN.posOS.xyz);
                OUT.uv = IN.uv;
                return OUT;
            }

            half4 frag(Varyings IN) : SV_Target
            {
                half4 col = SAMPLE_TEXTURE2D(_MainTex, sampler_MainTex, IN.uv);
                half noise = SAMPLE_TEXTURE2D(_NoiseTex, sampler_NoiseTex, IN.uv).r;
                clip(noise - _DissolveAmount);
                half edge = smoothstep(_DissolveAmount, _DissolveAmount + _EdgeWidth, noise);
                col.rgb = lerp(_EdgeColor.rgb, col.rgb, edge);
                return col;
            }
            ENDHLSL
        }
    }
}
```

### Post-Processing Volume Setup (C# template)
```csharp
// Source: Unity URP docs (Volume, VolumeProfile, Bloom, ColorAdjustments)
using UnityEngine;
using UnityEditor;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

public static class PostProcessingSetup
{
    [MenuItem("VeilBreakers/Scene/Setup Post-Processing")]
    public static void Setup()
    {
        var go = new GameObject("PostProcessing_Volume");
        var volume = go.AddComponent<Volume>();
        volume.isGlobal = true;
        volume.priority = 1;

        var profile = ScriptableObject.CreateInstance<VolumeProfile>();

        var bloom = profile.Add<Bloom>();
        bloom.intensity.Override(1.5f);
        bloom.threshold.Override(0.9f);
        bloom.scatter.Override(0.7f);

        var colorAdj = profile.Add<ColorAdjustments>();
        colorAdj.postExposure.Override(0.5f);
        colorAdj.contrast.Override(10f);
        colorAdj.saturation.Override(-10f);

        var vignette = profile.Add<Vignette>();
        vignette.intensity.Override(0.35f);

        volume.profile = profile;

        var profilePath = "Assets/Resources/VFX/DarkFantasyPostProcess.asset";
        AssetDatabase.CreateAsset(profile, profilePath);
        AssetDatabase.SaveAssets();
        Debug.Log("[VeilBreakers] Post-processing volume created.");
    }
}
```

### WCAG Contrast Ratio Check (Python)
```python
# Source: W3C WCAG 2.1 contrast ratio specification
# (https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio)
def relative_luminance(r: float, g: float, b: float) -> float:
    """Calculate relative luminance per W3C spec. RGB values 0-1."""
    def linearize(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)

def contrast_ratio(fg: tuple, bg: tuple) -> float:
    """WCAG contrast ratio between two RGB colors (0-255 each)."""
    l1 = relative_luminance(fg[0]/255, fg[1]/255, fg[2]/255)
    l2 = relative_luminance(bg[0]/255, bg[1]/255, bg[2]/255)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def check_wcag_aa(fg: tuple, bg: tuple, large_text: bool = False) -> bool:
    """Check WCAG 2.1 AA compliance. 4.5:1 normal, 3:1 large text."""
    ratio = contrast_ratio(fg, bg)
    threshold = 3.0 if large_text else 4.5
    return ratio >= threshold
```

### AnimatorController Creation (C# template)
```csharp
// Source: Unity docs (AnimatorController.CreateAnimatorControllerAtPath)
using UnityEngine;
using UnityEditor;
using UnityEditor.Animations;

public static class AnimatorSetup
{
    [MenuItem("VeilBreakers/Scene/Create Animator Controller")]
    public static void Create()
    {
        var controller = AnimatorController.CreateAnimatorControllerAtPath(
            "Assets/Animations/CreatureController.controller");

        controller.AddParameter("Speed", AnimatorControllerParameterType.Float);
        controller.AddParameter("IsAttacking", AnimatorControllerParameterType.Bool);
        controller.AddParameter("Die", AnimatorControllerParameterType.Trigger);

        var rootSM = controller.layers[0].stateMachine;
        var idleState = rootSM.AddState("Idle", new Vector3(200, 0, 0));
        var runState = rootSM.AddState("Run", new Vector3(400, 0, 0));
        var attackState = rootSM.AddState("Attack", new Vector3(400, 100, 0));
        var deathState = rootSM.AddState("Death", new Vector3(600, 0, 0));

        var idleToRun = idleState.AddTransition(runState);
        idleToRun.AddCondition(AnimatorConditionMode.Greater, 0.1f, "Speed");
        idleToRun.hasExitTime = false;

        var runToIdle = runState.AddTransition(idleState);
        runToIdle.AddCondition(AnimatorConditionMode.Less, 0.1f, "Speed");
        runToIdle.hasExitTime = false;

        var anyToAttack = rootSM.AddAnyStateTransition(attackState);
        anyToAttack.AddCondition(AnimatorConditionMode.If, 0, "IsAttacking");

        var anyToDeath = rootSM.AddAnyStateTransition(deathState);
        anyToDeath.AddCondition(AnimatorConditionMode.If, 0, "Die");

        AssetDatabase.SaveAssets();
        Debug.Log("[VeilBreakers] AnimatorController created.");
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Legacy Particle System (CPU) | VFX Graph (GPU) | Unity 2019+ | Orders of magnitude more particles; GPU compute shaders |
| Unity IMGUI / UGUI | UI Toolkit (UXML + USS) | Unity 2021+ | Web-like layout model, better theming, responsive design |
| Post Processing Stack v2 | URP/HDRP Volume system | Unity 2020+ | Integrated into render pipeline, no separate package |
| Manual AudioMixer | Still manual (no creation API) | N/A | Must use template approach or internal reflection |
| NavMesh window bake | NavMeshSurface component | Unity 2022+ | Runtime baking, per-surface control, NavMeshLinks |
| Mecanim (manual editor) | AnimatorController C# API | Unity 5+ | Full programmatic creation of states, transitions, blend trees |
| ElevenLabs SFX v1 | SFX v2 (Sept 2025) | Sept 2025 | 30s duration, loop support, 48kHz, better prompt adherence |

**Deprecated/outdated:**
- Post Processing Stack v2 (com.unity.postprocessing): Replaced by URP/HDRP Volume system
- Legacy Particle System: Still works but VFX Graph preferred for new projects
- IMGUI for game UI: Only for editor tools now; UI Toolkit for all game UI

## .mcp.json Configuration

The Unity MCP server needs to be added to `.mcp.json`. mcp-unity is a Unity Package Manager package (not npm); it runs a Node.js server from within the Unity project's `Packages/com.mcp.unity/Server~/` directory.

```json
{
  "mcpServers": {
    "vb-blender": {
      "type": "stdio",
      "command": "uv",
      "args": ["--directory", "Tools/mcp-toolkit", "run", "vb-blender-mcp"],
      "env": {
        "BLENDER_PORT": "9876",
        "BLENDER_HOST": "localhost"
      }
    },
    "mcp-unity": {
      "type": "stdio",
      "command": "node",
      "args": ["<UNITY_PROJECT>/Packages/com.mcp.unity/Server~/build/index.js"],
      "env": {
        "UNITY_PORT": "8090"
      }
    }
  }
}
```

Note: The exact path depends on where the Unity project lives. The user must install mcp-unity via Unity Package Manager first (`https://github.com/CoderGamester/mcp-unity.git`).

## Open Questions

1. **Unity project path configuration**
   - What we know: Python MCP toolkit needs to write files to the Unity project's Assets/ directory
   - What's unclear: Whether the user has a fixed Unity project path or it varies
   - Recommendation: Add `UNITY_PROJECT_PATH` env var to Settings; validate on startup; fail fast with clear error if not set

2. **ElevenLabs API key availability**
   - What we know: ElevenLabs SDK requires API key; some operations may be quota-limited
   - What's unclear: Whether the user has an ElevenLabs subscription and at what tier
   - Recommendation: Implement stub mode that returns placeholder audio files (silence or simple tones) when ELEVENLABS_API_KEY is not set; all audio tools work in both modes

3. **VFX Graph base assets**
   - What we know: VFX Graph cannot be created programmatically; need pre-made .vfx assets to configure
   - What's unclear: Whether the toolkit should ship base VFX Graph assets or expect them to exist
   - Recommendation: Ship minimal template VFX Graph assets (particle_emitter_base, trail_base, aura_base) as Unity package content; Python configures exposed properties

4. **AudioMixer creation strategy**
   - What we know: No public API to create AudioMixer programmatically
   - What's unclear: Whether internal reflection approach is stable across Unity versions
   - Recommendation: Ship a pre-built AudioMixer template .mixer asset; Python generates C# that loads and configures it rather than creating from scratch

5. **mcp-unity tool reliability after domain reload**
   - What we know: Domain reload drops WebSocket connection; server restarts after reload
   - What's unclear: Exact timing of server restart; whether retry logic is needed in Python layer
   - Recommendation: Implement retry-with-backoff wrapper for all mcp-unity calls that follow a recompile; 3 retries with 2s/4s/8s delays

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | `Tools/mcp-toolkit/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd Tools/mcp-toolkit && uv run pytest tests/ -x --tb=short -q` |
| Full suite command | `cd Tools/mcp-toolkit && uv run pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VFX-01 | VFX template generates valid C# for particle config | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_vfx_templates.py::test_particle_template -x` | Wave 0 |
| VFX-02 | Brand VFX config maps produce correct parameter sets | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_vfx_templates.py::test_brand_vfx_configs -x` | Wave 0 |
| VFX-06 | Corruption shader template produces valid HLSL | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_vfx_templates.py::test_corruption_shader -x` | Wave 0 |
| VFX-07 | Shader templates (dissolve/force field/water/etc.) generate valid HLSL | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_vfx_templates.py::test_shader_templates -x` | Wave 0 |
| VFX-08 | Post-processing template generates valid C# | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_vfx_templates.py::test_post_processing_template -x` | Wave 0 |
| AUD-01 | ElevenLabs client calls SFX endpoint correctly | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_elevenlabs_client.py::test_sfx_generation -x` | Wave 0 |
| AUD-02 | Music loop generation with loop=True parameter | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_elevenlabs_client.py::test_music_loop -x` | Wave 0 |
| AUD-03 | Voice line synthesis calls TTS endpoint | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_elevenlabs_client.py::test_voice_synthesis -x` | Wave 0 |
| AUD-05 | Footstep manager template generates valid C# | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_audio_templates.py::test_footstep_manager -x` | Wave 0 |
| AUD-08 | Audio mixer setup template generates valid C# | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_audio_templates.py::test_mixer_setup -x` | Wave 0 |
| AUD-09 | Audio pool manager template generates valid C# | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_audio_templates.py::test_pool_manager -x` | Wave 0 |
| UI-02 | UXML layout validation detects overlaps and zero-size | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_ui_validation.py::test_layout_validation -x` | Wave 0 |
| UI-05 | UXML/USS generation from description spec | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_ui_templates.py::test_uxml_generation -x` | Wave 0 |
| UI-06 | WCAG contrast ratio calculation correct | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_wcag_checker.py -x` | Wave 0 |
| UI-07 | Screenshot diff detects visual regression | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_screenshot_diff.py -x` | Wave 0 |
| SCENE-01 | Terrain setup template generates valid C# | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_scene_templates.py::test_terrain_setup -x` | Wave 0 |
| SCENE-04 | NavMesh bake template generates valid C# | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_scene_templates.py::test_navmesh_setup -x` | Wave 0 |
| SCENE-05 | Animator controller template generates valid C# | unit | `cd Tools/mcp-toolkit && uv run pytest tests/test_scene_templates.py::test_animator_setup -x` | Wave 0 |

Note: "Valid C#" means the generated string contains expected class names, method signatures, Unity API calls, and parameter values. Actual C# compilation is verified by Unity after file write + recompile.

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && uv run pytest tests/ -x --tb=short -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_vfx_templates.py` -- covers VFX-01, VFX-02, VFX-06, VFX-07, VFX-08
- [ ] `tests/test_elevenlabs_client.py` -- covers AUD-01, AUD-02, AUD-03, AUD-04
- [ ] `tests/test_audio_templates.py` -- covers AUD-05, AUD-06, AUD-08, AUD-09, AUD-10
- [ ] `tests/test_ui_templates.py` -- covers UI-05
- [ ] `tests/test_ui_validation.py` -- covers UI-02
- [ ] `tests/test_wcag_checker.py` -- covers UI-06
- [ ] `tests/test_screenshot_diff.py` -- covers UI-07
- [ ] `tests/test_scene_templates.py` -- covers SCENE-01 through SCENE-07
- [ ] `tests/test_editor_templates.py` -- covers auto-recompile, play mode, screenshot
- [ ] `src/veilbreakers_mcp/shared/elevenlabs_client.py` -- ElevenLabs API wrapper
- [ ] `src/veilbreakers_mcp/shared/unity_templates/` -- all template modules
- [ ] `src/veilbreakers_mcp/shared/wcag_checker.py` -- WCAG contrast calculation
- [ ] `src/veilbreakers_mcp/shared/screenshot_diff.py` -- image comparison

## Sources

### Primary (HIGH confidence)
- Unity VFX Graph Component API: https://docs.unity3d.com/Packages/com.unity.visualeffectgraph@7.1/manual/ComponentAPI.html -- SetFloat/SetVector4/SetGradient for exposed property control
- Unity AnimatorController API: https://docs.unity3d.com/ScriptReference/Animations.AnimatorController.html -- CreateAnimatorControllerAtPath, AddParameter, AddState, AddTransition
- Unity EditorApplication API: https://docs.unity3d.com/ScriptReference/EditorApplication.html -- EnterPlaymode(), isPlaying, playModeStateChanged
- Unity AssetDatabase.Refresh: https://docs.unity3d.com/ScriptReference/AssetDatabase.Refresh.html -- triggers import and compilation of new files
- Unity TerrainData API: https://docs.unity3d.com/ScriptReference/TerrainData.html -- SetHeights(), SetAlphamaps()
- Unity ScreenCapture: https://docs.unity3d.com/ScriptReference/ScreenCapture.CaptureScreenshot.html -- game view capture
- ElevenLabs SFX API: https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert -- POST endpoint, text/duration/loop params
- ElevenLabs Python SDK (PyPI): https://pypi.org/project/elevenlabs/ -- v2.39.0, text_to_sound_effects.convert() and text_to_speech.convert()
- mcp-unity (CoderGamester): https://github.com/CoderGamester/mcp-unity -- v1.2.0, 25 tools including recompile_scripts, execute_menu_item
- W3C WCAG 2.1 Contrast Ratio: https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio -- relative luminance formula

### Secondary (MEDIUM confidence)
- Unity VFX Graph creation limitations: https://discussions.unity.com/t/is-it-possible-to-edit-the-vfx-graph-from-script/931719 -- confirmed no public creation API
- Unity Shader Graph JSON format: Community discussion confirming undocumented/unstable internal format
- Cinemachine Impulse: https://docs.unity3d.com/Packages/com.unity.cinemachine@3.1/manual/CinemachineImpulse.html -- GenerateImpulse() for camera shake
- Animation Rigging TwoBoneIKConstraint: https://docs.unity3d.com/Packages/com.unity.animation.rigging@1.3/manual/constraints/TwoBoneIKConstraint.html

### Tertiary (LOW confidence)
- AudioMixer creation via internal API/reflection: Multiple community discussions suggest using SerializedObject on AudioMixerController, but no official documentation supports this approach. Template .mixer asset is the safer alternative.
- mcp-unity domain reload timing: AGENTS.md mentions connection drops but doesn't specify exact reconnection timing. 2-5 second delay is an estimate based on typical Unity reload times.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - ElevenLabs SDK version verified via pip, mcp-unity verified via GitHub releases, all Unity APIs verified via official docs
- Architecture: HIGH - Code generation pattern is well-established; mcp-unity's tool set confirmed via AGENTS.md; VFX/Shader Graph limitations verified through multiple sources
- Pitfalls: HIGH - Domain reload issue documented in mcp-unity CLAUDE.md; VFX/Shader Graph API limitations confirmed by official forums; AudioMixer limitation confirmed by multiple community sources
- Audio integration: MEDIUM - ElevenLabs API endpoints verified but exact output format handling (iterator to bytes) needs validation during implementation
- mcp-unity reliability: MEDIUM - Tool list confirmed but parameter schemas not fully documented; retry logic timing is estimated

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable domain -- Unity APIs change slowly; ElevenLabs SDK updates frequently but backwards-compatible)
