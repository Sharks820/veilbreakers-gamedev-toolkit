# Phase 10: C# Programming Framework - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** Auto-generated (--auto flag, recommended defaults selected)

<domain>
## Phase Boundary

General-purpose C# code generation and modification for Unity — not limited to domain-specific templates. Covers: arbitrary class types (MonoBehaviour, plain class, interface, enum, struct, static utility), script modification (add methods/fields/properties/attributes), custom Editor tools (EditorWindow, PropertyDrawer, Inspector drawers, SceneView overlays), Unity Test Framework integration (create tests, run tests, collect results), reusable architecture patterns (service locator, event bus, object pool, state machine, observer), and HLSL/ShaderLab shader writing (arbitrary shaders, custom ScriptableRendererFeatures).

Requirements: CODE-01, CODE-02, CODE-03, CODE-04, CODE-05, CODE-06, CODE-07, CODE-08, CODE-09, CODE-10, SHDR-01, SHDR-02.

</domain>

<decisions>
## Implementation Decisions

### Code Generation Approach
- **Structured template with sections**: Generate C# using structured section builders (using statements, namespace declaration, class attributes, class body with fields/properties/methods) with proper indentation — not raw string concatenation
- **Match VeilBreakers conventions**: Generated code uses `_camelCase` private fields, PascalCase properties/methods, `VeilBreakers.[Category]` namespaces, `k` prefix constants — matching the game project's 128 existing scripts
- **All C# class types supported**: MonoBehaviour, ScriptableObject, plain class, static class, interface, enum, struct, abstract class — each with appropriate boilerplate (using statements, attributes, base class)
- **Code generation is NOT execution**: The `unity_code` tool generates .cs files and writes them to the project. Compilation happens via `unity_editor` action=`recompile`. This follows the established two-step pattern from v1.0

### Script Modification
- **Regex-based insertion at markers**: Parse existing .cs files, find insertion points (end of class body, after last field declaration, after last method, after last using statement), insert new code with matched indentation
- **Preserve formatting**: Detect file's indentation style (tabs vs spaces, indent width) and match it in inserted code
- **Non-destructive modifications only**: Add methods, fields, properties, attributes, using statements. Never remove or replace existing code — that's manual refactoring territory
- **Backup before modify**: Create .cs.bak before any modification for easy revert

### Editor Tooling
- **EditorWindow generation**: Full window scaffolding with OnGUI/CreateGUI, menu item registration, serialization support
- **PropertyDrawer generation**: Custom drawer for any SerializedProperty type with proper height calculation
- **Inspector drawer generation**: Custom Editor for any MonoBehaviour/ScriptableObject with OnInspectorGUI
- **SceneView overlay generation**: Custom overlay panels for scene editing tools (Unity 2022.1+ Overlay API)

### Test Framework Integration
- **Create test assemblies**: Generate .asmdef for EditMode and PlayMode test assemblies with correct Unity Test Framework references (uses Phase 9's unity_assets asmdef generator)
- **Generate test classes**: NUnit test classes with [Test], [SetUp], [TearDown], [UnityTest] attributes
- **Run tests via CLI**: Execute Unity in batch mode with `-runTests` flag, parse NUnit XML results
- **Structured results through MCP**: Return pass/fail counts, failure messages, test names, duration — machine-readable JSON

### Architecture Patterns
- **Service locator** (CODE-06): Static registry with interface-based lookup, lazy initialization, scene-persistent option
- **Event bus with SO channels** (CODE-10): ScriptableObject-based event channels (GameEvent, GameEvent<T>), listener components, editor raise button
- **Generic object pool** (CODE-07): Pool<T> with configurable initial size, max size, auto-expand, warm-up. Works with GameObjects (Instantiate/SetActive) and plain objects
- **Reusable state machine** (CODE-09): Generic StateMachine<TState> with state enter/exit/update, transitions with conditions, current state tracking
- **Singleton patterns** (CODE-08): Persistent MonoBehaviour singleton (DontDestroyOnLoad), non-MonoBehaviour thread-safe singleton — matches VeilBreakers' existing SingletonMonoBehaviour<T> base class
- **Observer/event system** (CODE-10): Integrated with SO event channels above

### Shader Writing
- **Arbitrary HLSL/ShaderLab**: Generate complete .shader files with ShaderLab wrapper, Properties block, SubShader/Pass structure, vertex/fragment or surface shader code
- **Custom ScriptableRendererFeature**: Generate URP renderer features with custom render passes, configurable via ScriptableRendererData
- **Template-based with configurable properties**: Shader properties (floats, colors, textures, vectors) specified as parameters, auto-generated Properties block and variable declarations

### Claude's Discretion
- Exact regex patterns for script modification insertion points
- C# code formatting engine implementation details
- Test runner timeout and retry configuration
- Architecture pattern default configurations and naming
- ShaderLab boilerplate structure for different shader types
- Whether to use Roslyn for AST analysis (recommended: no, too heavy for MCP context)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### VeilBreakers Game Project (conventions to match)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Core/SingletonMonoBehaviour.cs` — Existing singleton base class (CODE-08 must be compatible)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Core/EventBus.cs` — Existing 50+ event system (CODE-10 SO channels should complement, not replace)
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Scripts/Core/Constants.cs` — Naming conventions reference
- `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent/Assets/Editor/` — Existing editor tools (CODE-03 should follow same patterns)

### Toolkit Implementation (extend these)
- `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` — Add unity_code and unity_shader compound tools
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/` — Template generator pattern
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/shader_templates.py` — Existing shader generators (SHDR-01/02 extends this)

### Requirements
- `.planning/REQUIREMENTS.md` — CODE-01 through CODE-10, SHDR-01, SHDR-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_write_to_unity()`: Path-validated file writer — all new tools use this
- `_sanitize_cs_string()` / `_sanitize_cs_identifier()`: String/identifier sanitization
- `_read_unity_result()`: Result JSON reader from Temp/vb_result.json
- `unity_editor` action=`recompile`: Already handles AssetDatabase.Refresh
- Phase 9's `unity_assets` action=`create_asmdef`: Assembly definition creation for test assemblies
- Phase 9's `unity_prefab` action=`reflect_component`: SerializedObject field discovery

### Established Patterns
- **Compound tool pattern**: 5-10 actions per tool
- **Handler + template pattern**: async handler dispatches to template generator
- **Enhanced result JSON**: `changed_assets`, `warnings`, `validation_status`
- **Undo protocol**: All mutations use Undo registration
- VeilBreakers game uses `VeilBreakers.[Category]` namespaces consistently

### Integration Points
- `unity_code` tool will be the primary new compound tool (CODE-01 through CODE-10)
- `unity_shader` tool extends existing shader_templates.py (SHDR-01, SHDR-02)
- Test runner integration may need a new action on `unity_editor` or its own tool
- Script modification reads existing .cs files from Unity project via settings.UNITY_PROJECT_PATH

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers already has SingletonMonoBehaviour<T> — CODE-08 singleton generation should extend this, not create a competing pattern
- EventBus with 50+ events exists — CODE-10 SO event channels should be a complementary approach for new systems, not a replacement
- The game has 4 existing Assembly Definitions — test assemblies should reference VeilBreakers.Runtime for testing game code
- Shader generation should target URP (Universal Render Pipeline) since the game uses URP 17.3.0
- Script modification must handle the game's existing 128 scripts safely — regex insertion should be conservative

</specifics>

<deferred>
## Deferred Ideas

None — auto-mode stayed within phase scope

</deferred>

---

*Phase: 10-c-programming-framework*
*Context gathered: 2026-03-20 via auto-mode*
