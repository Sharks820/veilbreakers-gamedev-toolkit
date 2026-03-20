# Phase 10: C# Programming Framework - Research

**Researched:** 2026-03-20
**Domain:** C# code generation / Unity editor scripting / HLSL shader writing / Unity Test Framework
**Confidence:** HIGH

## Summary

Phase 10 generalizes the toolkit's C# code generation capabilities from domain-specific templates (VFX, gameplay, audio) to arbitrary C# class generation, script modification, editor tooling, test framework integration, architecture pattern scaffolding, and custom shader writing. The existing codebase already has 11 template modules producing C# output for Unity, so Phase 10 extends this proven pattern with two new compound tools (`unity_code` and `unity_shader`) and new actions on `unity_editor` for test running.

The VeilBreakers game project uses Unity 6000.3.6f1 (Unity 6) with URP 17.3.0, Test Framework 1.6.0, and has 4 existing Assembly Definitions (VeilBreakers.Runtime, VeilBreakers.Editor, VeilBreakers.Tests.EditMode, VeilBreakers.Tests.PlayMode). The existing `SingletonMonoBehaviour<T>` and `EventBus` classes in the game project establish conventions that CODE-08 and CODE-10 must be compatible with. Code follows `VeilBreakers.[Category]` namespace patterns, `_camelCase` private fields, PascalCase public members, and `k` prefix constants.

**Primary recommendation:** Create `code_templates.py` for arbitrary C# generation (CODE-01 through CODE-10), extend `shader_templates.py` for arbitrary shader writing (SHDR-01/02), and add a `run_tests` action to `unity_editor` using TestRunnerApi for programmatic test execution with JSON result collection (CODE-04/05).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Code Generation Approach**: Structured template with sections (using statements, namespace, class attributes, class body with fields/properties/methods) with proper indentation -- not raw string concatenation
- **Match VeilBreakers conventions**: `_camelCase` private fields, PascalCase properties/methods, `VeilBreakers.[Category]` namespaces, `k` prefix constants
- **All C# class types supported**: MonoBehaviour, ScriptableObject, plain class, static class, interface, enum, struct, abstract class
- **Code generation is NOT execution**: `unity_code` tool generates .cs files. Compilation via `unity_editor` action=`recompile`. Two-step pattern.
- **Script Modification**: Regex-based insertion at markers (end of class body, after last field, after last method, after last using statement). Preserve formatting. Non-destructive only. Backup before modify (.cs.bak).
- **EditorWindow generation**: Full window scaffolding with OnGUI/CreateGUI, menu item registration, serialization support
- **PropertyDrawer generation**: Custom drawer for any SerializedProperty type with proper height calculation
- **Inspector drawer generation**: Custom Editor for any MonoBehaviour/ScriptableObject with OnInspectorGUI
- **SceneView overlay generation**: Custom overlay panels for scene editing tools (Unity 2022.1+ Overlay API)
- **Test assemblies**: Generate .asmdef for EditMode and PlayMode test assemblies with correct Unity Test Framework references (uses Phase 9's unity_assets asmdef generator)
- **Generate test classes**: NUnit test classes with [Test], [SetUp], [TearDown], [UnityTest] attributes
- **Run tests via CLI**: Execute Unity in batch mode with `-runTests` flag, parse NUnit XML results
- **Structured results through MCP**: Return pass/fail counts, failure messages, test names, duration -- machine-readable JSON
- **Service locator** (CODE-06): Static registry with interface-based lookup, lazy initialization, scene-persistent option
- **Event bus with SO channels** (CODE-10): ScriptableObject-based event channels (GameEvent, GameEvent<T>), listener components, editor raise button
- **Generic object pool** (CODE-07): Pool<T> with configurable initial size, max size, auto-expand, warm-up
- **Reusable state machine** (CODE-09): Generic StateMachine<TState> with state enter/exit/update, transitions with conditions
- **Singleton patterns** (CODE-08): Persistent MonoBehaviour singleton (DontDestroyOnLoad), non-MonoBehaviour thread-safe singleton -- must be compatible with VeilBreakers' existing SingletonMonoBehaviour<T>
- **Arbitrary HLSL/ShaderLab**: Generate complete .shader files with ShaderLab wrapper, Properties block, SubShader/Pass structure
- **Custom ScriptableRendererFeature**: Generate URP renderer features with custom render passes, configurable via ScriptableRendererData

### Claude's Discretion
- Exact regex patterns for script modification insertion points
- C# code formatting engine implementation details
- Test runner timeout and retry configuration
- Architecture pattern default configurations and naming
- ShaderLab boilerplate structure for different shader types
- Whether to use Roslyn for AST analysis (recommended: no, too heavy for MCP context)

### Deferred Ideas (OUT OF SCOPE)
None -- auto-mode stayed within phase scope

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CODE-01 | Generate arbitrary C# MonoBehaviours, plain classes, interfaces, enums, structs, static utilities | Section builder pattern in code_templates.py; class_type param selects boilerplate |
| CODE-02 | Modify existing C# scripts (add methods, fields, properties, attributes, using statements) | Regex insertion with indentation detection; .cs.bak backup; read via settings.UNITY_PROJECT_PATH |
| CODE-03 | Generate custom Inspector drawers, PropertyDrawers, EditorWindows, SceneView overlays | Editor tool templates with proper Unity Editor API usage; Overlay API for SceneView |
| CODE-04 | Create EditMode and PlayMode test assemblies, fixtures, test methods | Reuse Phase 9 generate_asmdef_script; NUnit attributes; Test Framework 1.6.0 asmdef structure |
| CODE-05 | Run Unity tests and collect pass/fail results through MCP | TestRunnerApi programmatic execution with ICallbacks; JSON result collection via vb_result.json |
| CODE-06 | Scaffold service locator, event bus, SO event channels | Static ServiceLocator<T> registry; complementary to existing EventBus |
| CODE-07 | Generate generic object pooling systems | Pool<T> with GameObject and plain object support; Instantiate/SetActive pattern |
| CODE-08 | Generate singleton patterns (persistent MB, non-MB) | Must extend existing SingletonMonoBehaviour<T>; non-MB thread-safe lazy pattern |
| CODE-09 | Generate generic reusable state machine framework | StateMachine<TState> with IState interface; transitions with conditions |
| CODE-10 | Generate observer/event system with SO event channels | GameEvent/GameEvent<T> SOs with GameEventListener MB; complement existing EventBus |
| SHDR-01 | Write arbitrary HLSL/ShaderLab shaders | Extend shader_templates.py with parameterized shader builder; URP 17.3.0 compatible |
| SHDR-02 | Create custom URP ScriptableRendererFeatures and render passes | RenderGraph API (RecordRenderGraph) for Unity 6; feature + pass class generation |

</phase_requirements>

## Standard Stack

### Core (Already in Project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Unity Editor | 6000.3.6f1 (Unity 6) | Target editor platform | VeilBreakers game project version |
| URP | 17.3.0 | Render pipeline | VeilBreakers uses URP; all shaders target this |
| Unity Test Framework | 1.6.0 | Test execution | Already installed in VeilBreakers project |
| NUnit | 3.x (bundled) | Test assertions/attributes | Bundled with Unity Test Framework |
| Python | 3.12+ | MCP server runtime | Per pyproject.toml |
| FastMCP | 1.26.0+ | MCP protocol server | Existing tool server framework |
| pytest | 8.0+ | Python-side test framework | Toolkit test infrastructure |

### Supporting (Existing Toolkit Patterns)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.0+ | Settings/config management | `settings.unity_project_path` for file I/O |
| re (stdlib) | N/A | Regex for script modification | CODE-02 insertion point detection |
| pathlib (stdlib) | N/A | Path operations | File reading/writing with path traversal protection |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex-based script modification | Roslyn AST parsing | Roslyn is too heavy for MCP context (~200MB+ dependency); regex is sufficient for additive-only modifications |
| TestRunnerApi (programmatic) | CLI batch mode `-runTests` | CLI requires spawning a separate Unity process; TestRunnerApi runs in-editor and integrates with existing two-step pattern |
| String template building | Jinja2 templates | Adds external dependency; f-string templates match existing codebase pattern across 11 template modules |

## Architecture Patterns

### Recommended Project Structure
```
Tools/mcp-toolkit/src/veilbreakers_mcp/
  shared/unity_templates/
    code_templates.py         # NEW: CODE-01 through CODE-10 generators
    shader_templates.py       # EXTEND: add arbitrary shader + renderer feature generators
    editor_templates.py       # Minor extension: test runner script generator
  unity_server.py             # EXTEND: add unity_code + unity_shader compound tools
                              #         add run_tests action to unity_editor

Tools/mcp-toolkit/tests/
  test_code_templates.py      # NEW: unit tests for code generators
  test_shader_templates_v2.py # NEW: unit tests for new shader generators
  test_csharp_syntax_deep.py  # EXTEND: add new generators to syntax checks
```

### Pattern 1: Section-Based C# Code Builder
**What:** Build C# source strings by assembling sections (usings, namespace open, class declaration, fields, properties, methods, namespace close) with proper indentation tracking.
**When to use:** All CODE-01 class generation.
**Example:**
```python
# Source: Established pattern in existing templates, evolved for generality
def _build_cs_class(
    class_name: str,
    class_type: str,  # "class", "static class", "abstract class", "struct", "interface", "enum"
    namespace: str = "",
    base_class: str = "",
    interfaces: list[str] | None = None,
    usings: list[str] | None = None,
    attributes: list[str] | None = None,
    fields: list[dict] | None = None,
    properties: list[dict] | None = None,
    methods: list[dict] | None = None,
    enum_values: list[str] | None = None,
) -> str:
    """Build a complete C# source file from structured sections."""
    lines = []
    # 1. Using statements
    for u in (usings or ["UnityEngine"]):
        lines.append(f"using {u};")
    lines.append("")
    # 2. Namespace open
    indent = ""
    if namespace:
        lines.append(f"namespace {namespace}")
        lines.append("{")
        indent = "    "
    # 3. Class attributes
    for attr in (attributes or []):
        lines.append(f"{indent}[{attr}]")
    # 4. Class declaration
    decl = f"{indent}public {class_type} {class_name}"
    inheritance = []
    if base_class:
        inheritance.append(base_class)
    if interfaces:
        inheritance.extend(interfaces)
    if inheritance:
        decl += " : " + ", ".join(inheritance)
    lines.append(decl)
    lines.append(f"{indent}{{")
    # 5. Fields, properties, methods with indent+4
    # ... (body generation)
    lines.append(f"{indent}}}")
    if namespace:
        lines.append("}")
    return "\n".join(lines) + "\n"
```

### Pattern 2: Regex-Based Script Modification (CODE-02)
**What:** Read existing .cs file, detect indentation style, find insertion points using regex, insert new code at the correct location.
**When to use:** Adding methods, fields, properties, attributes, using statements to existing scripts.
**Example:**
```python
# Insertion point patterns
INSERTION_POINTS = {
    "after_last_using": r"(^using\s+[^;]+;\s*$)(?!.*^using\s)",
    "after_last_field": r"(^\s+(?:private|protected|public|internal)\s+(?!(?:void|static\s+void|override|virtual|async)\s)\w+[\w<>\[\],\s]*\s+_?\w+\s*[;=])",
    "after_last_method": r"(^\s+\})\s*$(?=\s*\})",  # last closing brace before class close
    "end_of_class": r"^(\s*)\}\s*$(?=\s*\}\s*$)",  # second-to-last closing brace
}
```

### Pattern 3: Compound Tool Registration
**What:** New compound tools follow the established pattern: Literal action type, param validation, handler dispatch, template generation, _write_to_unity, JSON response with next_steps.
**When to use:** All new tool registrations.
**Key insight:** unity_server.py is already 4,492 lines. The handler functions should stay thin (dispatch to template generators in separate files).

### Anti-Patterns to Avoid
- **Monolithic template functions:** Each template function should do ONE thing. Don't combine class generation with file writing. The handler does writing; the template returns a string.
- **Regex replacement instead of insertion:** CODE-02 must be additive only. Never use regex to replace or remove existing code -- that's manual refactoring territory.
- **Ignoring existing conventions:** CODE-08 singletons MUST be compatible with the existing `SingletonMonoBehaviour<T>` in `VeilBreakers.Core`. CODE-10 SO events must complement, not replace, the existing `EventBus`.
- **Hard-coded indentation:** Detect whether existing file uses tabs or spaces before inserting. The VeilBreakers codebase uses 4-space indentation.
- **Skipping sanitization:** All user-supplied strings MUST go through `_sanitize_cs_string()` before embedding in C# templates. All identifiers through `_sanitize_cs_identifier()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test assembly definitions | Custom asmdef JSON builder | Phase 9's `generate_asmdef_script()` | Already handles all asmdef fields; just pass correct test framework references |
| NUnit XML parsing | Custom XML parser | Python `xml.etree.ElementTree` stdlib | NUnit XML schema is well-defined; stdlib handles it perfectly |
| C# string escaping | Custom escaper | Existing `_sanitize_cs_string()` | Already battle-tested across 11 template modules |
| File writing to Unity project | Custom file writer | Existing `_write_to_unity()` | Has path traversal protection, directory creation, encoding |
| Shader URP include paths | Per-shader include management | `_URP_CORE_INCLUDE` constant from shader_templates.py | Centralized, already correct for URP 17 |

**Key insight:** Phase 9 built substantial infrastructure (`_write_to_unity`, `_read_unity_result`, `_sanitize_*`, `generate_asmdef_script`) that Phase 10 should reuse extensively. The main new work is the template generators themselves.

## Common Pitfalls

### Pitfall 1: Test Assembly Definition Configuration
**What goes wrong:** Generated test assemblies fail to compile because they're missing required references or have wrong settings.
**Why it happens:** Unity Test Framework requires very specific asmdef configuration: `overrideReferences: true`, `precompiledReferences: ["nunit.framework.dll"]`, `defineConstraints: ["UNITY_INCLUDE_TESTS"]`, `autoReferenced: false`, and references to `UnityEngine.TestRunner` + `UnityEditor.TestRunner`.
**How to avoid:** Use the existing VeilBreakers test assembly definitions as the template. The EditMode asmdef at `Assets/Tests/EditMode/VeilBreakers.Tests.EditMode.asmdef` is the canonical reference:
```json
{
  "overrideReferences": true,
  "precompiledReferences": ["nunit.framework.dll"],
  "defineConstraints": ["UNITY_INCLUDE_TESTS"],
  "autoReferenced": false,
  "references": ["UnityEngine.TestRunner", "UnityEditor.TestRunner", "VeilBreakers.Runtime"]
}
```
**Warning signs:** "NUnit.Framework not found" compile errors; tests not appearing in Test Runner window.

### Pitfall 2: TestRunnerApi vs CLI Batch Mode for Test Execution
**What goes wrong:** Using CLI batch mode (`-runTests`) requires spawning a separate Unity process, which conflicts with the MCP two-step pattern where scripts run inside the already-open editor.
**Why it happens:** The CONTEXT.md specifies "Run tests via CLI" but the existing architecture generates editor scripts that execute inside Unity.
**How to avoid:** Use `TestRunnerApi` programmatically via a generated C# editor script (matching existing pattern). The script uses `TestRunnerApi.Execute()` with `runSynchronously = true`, collects results via `ICallbacks`, and writes JSON to `Temp/vb_result.json`. This keeps the two-step pattern intact. CLI batch mode remains as a documented fallback for CI/CD scenarios.
**Warning signs:** MCP tool returns "pending" because it expects vb_result.json but a separate Unity process wrote results elsewhere.

### Pitfall 3: Script Modification Regex Breaking on Edge Cases
**What goes wrong:** Regex patterns for insertion points match incorrectly in files with unusual formatting, nested classes, or comments containing code-like text.
**Why it happens:** C# is not a regular language; regex cannot parse it fully.
**How to avoid:** Use conservative patterns that look for specific structural markers. Always create .cs.bak backup before modification. Validate the modified file has balanced braces. Only support single-class files (no nested class insertion). Reject files with ambiguous structure and return an error suggesting manual modification.
**Warning signs:** Mismatched brace count after modification; code inserted at wrong indentation level.

### Pitfall 4: URP 17 RenderGraph API vs Legacy Execute()
**What goes wrong:** Generated ScriptableRendererFeatures use the legacy `Execute()` method, which is obsolete in URP 17 / Unity 6.
**Why it happens:** Most online tutorials and documentation show the old API (`OnCameraSetup`, `Execute`, `OnCameraCleanup`).
**How to avoid:** Use `RecordRenderGraph(RenderGraph, ContextContainer)` method for ScriptableRenderPass. The compatibility mode is enabled by default for upgraded projects but new features should use the current API.
**Warning signs:** Deprecation warnings about `Execute` and `OnCameraSetup` in Unity console.

### Pitfall 5: Namespace Collisions with Existing EventBus
**What goes wrong:** Generated SO event channels use the same names or namespace as the existing `VeilBreakers.Core.EventBus`, causing compile errors or confusion.
**Why it happens:** CODE-10 adds a new event pattern alongside 50+ existing static events in EventBus.cs.
**How to avoid:** Use a distinct namespace (`VeilBreakers.Events.Channels`) and naming convention (`GameEvent_*` or `*EventChannel`) that clearly differentiates SO channels from static EventBus events. Document that SO channels are for new systems; existing EventBus continues for existing code.
**Warning signs:** Ambiguous event references; developers unsure which system to use.

### Pitfall 6: Generated Code Fails Sanitization of User Input
**What goes wrong:** User-supplied class names, method names, or field names contain characters that break C# compilation.
**Why it happens:** Users may pass names with spaces, special characters, or C# reserved words.
**How to avoid:** All identifiers go through `_sanitize_cs_identifier()`. Additionally, check for C# reserved words (`class`, `void`, `int`, `string`, etc.) and prefix with `@` if necessary. Validate that sanitized identifiers are not empty.
**Warning signs:** Generated .cs file fails to compile with syntax errors on identifiers.

## Code Examples

### Test Runner Editor Script (CODE-05)
```csharp
// Source: Verified against Unity Test Framework 1.6.0 API and existing vb_result.json pattern
using UnityEngine;
using UnityEditor;
using UnityEditor.TestTools.TestRunner.Api;
using System.IO;
using System.Collections.Generic;
using System.Text;

public static class VeilBreakers_RunTests
{
    [MenuItem("VeilBreakers/Code/Run Tests")]
    public static void Execute()
    {
        var api = ScriptableObject.CreateInstance<TestRunnerApi>();
        var collector = new TestResultCollector();
        api.RegisterCallbacks(collector);

        api.Execute(new ExecutionSettings
        {
            runSynchronously = true,
            filters = new[] { new Filter {
                testMode = TestMode.EditMode,
                // assemblyNames set dynamically
            }}
        });

        // Write structured JSON result
        var json = JsonUtility.ToJson(collector.BuildResult(), true);
        File.WriteAllText("Temp/vb_result.json", json);
        Debug.Log($"[VeilBreakers] Tests complete: {collector.PassCount} passed, {collector.FailCount} failed");
    }
}

// ICallbacks implementation for result collection
public class TestResultCollector : ICallbacks
{
    public int PassCount;
    public int FailCount;
    public List<TestDetail> Details = new();

    public void RunStarted(ITestAdaptor testsToRun) { }
    public void RunFinished(ITestResultAdaptor result)
    {
        PassCount = result.PassCount;
        FailCount = result.FailCount;
    }
    public void TestStarted(ITestAdaptor test) { }
    public void TestFinished(ITestResultAdaptor result)
    {
        if (!result.HasChildren)
        {
            Details.Add(new TestDetail {
                name = result.Test.FullName,
                passed = result.TestStatus == TestStatus.Passed,
                duration = (float)result.Duration,
                message = result.Message ?? ""
            });
        }
    }

    [System.Serializable]
    public class TestDetail { public string name; public bool passed; public float duration; public string message; }

    [System.Serializable]
    public class TestResult
    {
        public string status;
        public string action;
        public int pass_count;
        public int fail_count;
        public List<TestDetail> tests;
    }

    public TestResult BuildResult() => new TestResult {
        status = FailCount == 0 ? "success" : "failure",
        action = "run_tests",
        pass_count = PassCount,
        fail_count = FailCount,
        tests = Details
    };
}
```

### ScriptableObject Event Channel (CODE-10)
```csharp
// Source: Official Unity pattern (unity.com/how-to/scriptableobjects-event-channels-game-code)
using UnityEngine;
using System;

namespace VeilBreakers.Events.Channels
{
    /// <summary>
    /// ScriptableObject-based event channel (no-parameter).
    /// Complements VeilBreakers.Core.EventBus for new decoupled systems.
    /// </summary>
    [CreateAssetMenu(menuName = "VeilBreakers/Events/Game Event", fileName = "NewGameEvent")]
    public class GameEvent : ScriptableObject
    {
        private Action _onRaise;

        public void RegisterListener(Action listener) => _onRaise += listener;
        public void UnregisterListener(Action listener) => _onRaise -= listener;

        public void Raise()
        {
            _onRaise?.Invoke();
            #if UNITY_EDITOR
            Debug.Log($"[GameEvent] {name} raised");
            #endif
        }
    }
}
```

### Generic Object Pool (CODE-07)
```csharp
// Source: Standard Unity pooling pattern, adapted for VeilBreakers conventions
using UnityEngine;
using System;
using System.Collections.Generic;

namespace VeilBreakers.Patterns
{
    public class ObjectPool<T> where T : class
    {
        private readonly Stack<T> _available;
        private readonly Func<T> _createFunc;
        private readonly Action<T> _onGet;
        private readonly Action<T> _onRelease;
        private readonly int _maxSize;

        public int CountActive { get; private set; }
        public int CountInactive => _available.Count;

        public ObjectPool(
            Func<T> createFunc,
            Action<T> onGet = null,
            Action<T> onRelease = null,
            int initialSize = 10,
            int maxSize = 100)
        {
            _createFunc = createFunc ?? throw new ArgumentNullException(nameof(createFunc));
            _onGet = onGet;
            _onRelease = onRelease;
            _maxSize = maxSize;
            _available = new Stack<T>(initialSize);

            // Warm up
            for (int i = 0; i < initialSize; i++)
                _available.Push(_createFunc());
        }

        public T Get()
        {
            T item = _available.Count > 0 ? _available.Pop() : _createFunc();
            _onGet?.Invoke(item);
            CountActive++;
            return item;
        }

        public void Release(T item)
        {
            _onRelease?.Invoke(item);
            CountActive--;
            if (_available.Count < _maxSize)
                _available.Push(item);
        }
    }
}
```

### ScriptableRendererFeature for URP 17 (SHDR-02)
```csharp
// Source: Unity 6000.3.x docs - ScriptableRendererFeature with RenderGraph API
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.Rendering.RenderGraphModule;

public class CustomEffectFeature : ScriptableRendererFeature
{
    [SerializeField] private Shader _shader;
    [SerializeField] private CustomEffectSettings _settings;
    private Material _material;
    private CustomEffectPass _pass;

    public override void Create()
    {
        if (_shader != null)
            _material = CoreUtils.CreateEngineMaterial(_shader);
        _pass = new CustomEffectPass(_material, _settings);
        _pass.renderPassEvent = RenderPassEvent.BeforeRenderingPostProcessing;
    }

    public override void AddRenderPasses(ScriptableRenderer renderer, ref RenderingData renderingData)
    {
        if (_material != null && renderingData.cameraData.cameraType == CameraType.Game)
            renderer.EnqueuePass(_pass);
    }

    protected override void Dispose(bool disposing)
    {
        CoreUtils.Destroy(_material);
    }

    [System.Serializable]
    public class CustomEffectSettings
    {
        [Range(0f, 1f)] public float intensity = 0.5f;
    }
}

public class CustomEffectPass : ScriptableRenderPass
{
    private Material _material;
    private CustomEffectFeature.CustomEffectSettings _settings;

    public CustomEffectPass(Material material, CustomEffectFeature.CustomEffectSettings settings)
    {
        _material = material;
        _settings = settings;
    }

    public override void RecordRenderGraph(RenderGraph renderGraph, ContextContainer frameData)
    {
        var resourceData = frameData.Get<UniversalResourceData>();
        if (resourceData.isActiveTargetBackBuffer) return;

        var src = resourceData.activeColorTexture;
        var desc = renderGraph.GetTextureDesc(src);
        desc.depthBufferBits = 0;
        var dst = renderGraph.CreateTexture(desc);

        _material.SetFloat("_Intensity", _settings.intensity);

        var blitParams = new RenderGraphUtils.BlitMaterialParameters(src, dst, _material, 0);
        renderGraph.AddBlitPass(blitParams, "CustomEffect");

        var copyBack = new RenderGraphUtils.BlitMaterialParameters(dst, src, _material, 0);
        renderGraph.AddBlitPass(copyBack, "CustomEffectCopyBack");
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `ScriptableRenderPass.Execute()` | `RecordRenderGraph()` via RenderGraph API | URP 17 / Unity 6 (2024) | All new renderer features should use RenderGraph; `Execute()` is obsolete |
| EditorWindow `OnGUI()` (IMGUI) | `CreateGUI()` with UI Toolkit | Unity 2021.2+ | CreateGUI is modern approach; OnGUI still works but is legacy |
| PlayMode test `optionalUnityReferences: ["TestAssemblies"]` | `references: ["UnityEngine.TestRunner"]` with `overrideReferences` | Test Framework 1.3+ | The old PlayMode asmdef format is deprecated |
| TestRunnerApi instance method `Execute()` | Static `TestRunnerApi.ExecuteTestRun()` | Test Framework 2.0 (experimental) | 1.6.0 (VeilBreakers version) still uses instance methods |

**Deprecated/outdated:**
- `ScriptableRenderPass.OnCameraSetup/Execute/OnCameraCleanup`: Replaced by `RecordRenderGraph` in URP 17. Compatibility mode exists for upgraded projects but new code should use current API.
- VeilBreakers' PlayMode test asmdef uses old format (`optionalUnityReferences` instead of proper `references`). Phase 10 generated test assemblies should use the modern format.

## Open Questions

1. **EditorWindow: OnGUI vs CreateGUI**
   - What we know: CreateGUI is the modern UI Toolkit approach; OnGUI (IMGUI) still works and is simpler for quick editor tools.
   - What's unclear: CONTEXT.md says "OnGUI/CreateGUI" -- should we support both or default to one?
   - Recommendation: Default to IMGUI (OnGUI) for editor windows since it's simpler to generate as template strings and matches existing editor tools in the VeilBreakers project (e.g., SceneAuditor.cs uses IMGUI). Support CreateGUI as an optional parameter for more complex UI Toolkit-based windows.

2. **TestRunnerApi.Execute with runSynchronously and PlayMode tests**
   - What we know: `runSynchronously = true` works for EditMode tests. PlayMode tests require entering Play Mode and may not support synchronous execution.
   - What's unclear: Whether Test Framework 1.6.0 supports `runSynchronously` for PlayMode.
   - Recommendation: Default to EditMode for `run_tests` action. Support PlayMode as a parameter but document that results may require waiting and a second read of vb_result.json.

3. **RenderGraph API stability for generated code**
   - What we know: URP 17.3.0 uses RenderGraph API with `RecordRenderGraph`. The API is available and functional.
   - What's unclear: Whether the API has breaking changes between URP 17.x patch versions.
   - Recommendation: Use the current API as documented in Unity 6000.3.x. Pin to established patterns from the official URP RenderGraph Samples.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio |
| Config file | `Tools/mcp-toolkit/pyproject.toml` ([tool.pytest.ini_options]) |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_code_templates.py -x` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CODE-01 | Generate all C# class types, compile-ready | unit | `pytest tests/test_code_templates.py::TestGenerateClass -x` | No -- Wave 0 |
| CODE-02 | Modify existing scripts with correct insertion | unit | `pytest tests/test_code_templates.py::TestModifyScript -x` | No -- Wave 0 |
| CODE-03 | Generate editor tools (EditorWindow, PropertyDrawer, Inspector, Overlay) | unit | `pytest tests/test_code_templates.py::TestEditorTools -x` | No -- Wave 0 |
| CODE-04 | Generate test assemblies and test classes | unit | `pytest tests/test_code_templates.py::TestGenerateTests -x` | No -- Wave 0 |
| CODE-05 | Test runner script generates correct C# with TestRunnerApi | unit | `pytest tests/test_code_templates.py::TestRunnerScript -x` | No -- Wave 0 |
| CODE-06 | Service locator pattern generates valid C# | unit | `pytest tests/test_code_templates.py::TestServiceLocator -x` | No -- Wave 0 |
| CODE-07 | Object pool pattern generates valid C# | unit | `pytest tests/test_code_templates.py::TestObjectPool -x` | No -- Wave 0 |
| CODE-08 | Singleton patterns compatible with existing base class | unit | `pytest tests/test_code_templates.py::TestSingleton -x` | No -- Wave 0 |
| CODE-09 | State machine pattern generates valid C# | unit | `pytest tests/test_code_templates.py::TestStateMachine -x` | No -- Wave 0 |
| CODE-10 | SO event channels generate valid C# | unit | `pytest tests/test_code_templates.py::TestSOEvents -x` | No -- Wave 0 |
| SHDR-01 | Arbitrary shader generation with correct ShaderLab | unit | `pytest tests/test_shader_templates_v2.py::TestArbitraryShader -x` | No -- Wave 0 |
| SHDR-02 | ScriptableRendererFeature generation with RenderGraph API | unit | `pytest tests/test_shader_templates_v2.py::TestRendererFeature -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_code_templates.py tests/test_shader_templates_v2.py -x`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_code_templates.py` -- covers CODE-01 through CODE-10
- [ ] `tests/test_shader_templates_v2.py` -- covers SHDR-01, SHDR-02
- [ ] `tests/test_csharp_syntax_deep.py` -- needs extension with new generators

## Sources

### Primary (HIGH confidence)
- VeilBreakers game project source code (`C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/`) -- SingletonMonoBehaviour.cs, EventBus.cs, Constants.cs, all 4 asmdef files, ProjectVersion.txt, manifest.json
- Existing toolkit codebase (`Tools/mcp-toolkit/src/veilbreakers_mcp/`) -- unity_server.py (4,492 lines), 11 template modules, shader_templates.py, asset_templates.py
- Unity Test Framework 1.6.0 docs: [CLI reference](https://docs.unity3d.com/Packages/com.unity.test-framework@1.4/manual/reference-command-line.html), [TestRunnerApi](https://docs.unity3d.com/Packages/com.unity.test-framework@1.1/manual/reference-test-runner-api.html), [ICallbacks](https://docs.unity3d.com/Packages/com.unity.test-framework@1.1/manual/reference-icallbacks.html)

### Secondary (MEDIUM confidence)
- [Unity ScriptableRendererFeature example (Unity 6)](https://docs.unity3d.com/6000.1/Documentation/Manual/urp/renderer-features/create-custom-renderer-feature.html) -- RenderGraph API pattern
- [Unity EditorWindow CreateGUI](https://docs.unity3d.com/ScriptReference/EditorWindow.CreateGUI.html) -- CreateGUI vs OnGUI
- [Unity Overlay API](https://docs.unity3d.com/6000.0/Documentation/Manual/overlays-custom.html) -- SceneView overlay implementation
- [Unity SO event channels](https://unity.com/how-to/scriptableobjects-event-channels-game-code) -- Official GameEvent pattern
- [TestRunnerApi gist](https://gist.github.com/extrawurst/cf91a196bb450ef743252bc731c3cd0b) -- Programmatic test execution example
- [URP 17 upgrade guide](https://docs.unity3d.com/6000.3/Documentation/Manual/urp/upgrade-guide-unity-6.html) -- RenderGraph migration

### Tertiary (LOW confidence)
- None -- all findings verified against primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- verified directly against VeilBreakers project manifest.json and ProjectVersion.txt
- Architecture: HIGH -- follows established patterns from 11 existing template modules in the codebase
- Pitfalls: HIGH -- derived from actual asmdef configurations in the game project and verified Unity API documentation
- Code examples: MEDIUM-HIGH -- verified against Unity docs and existing game code, but RenderGraph API specifics for URP 17.3.0 not tested in-editor

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (Unity 6 / URP 17 is stable; Test Framework 1.6.0 is stable)
