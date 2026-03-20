---
phase: 10-c-programming-framework
plan: 02
subsystem: shader-generation
tags: [hlsl, shaderlab, urp, rendergraph, scriptablerendererfeature, unity6]

# Dependency graph
requires:
  - phase: 08-vfx-shader-audio
    provides: "Existing shader_templates.py with 7 VFX shader generators"
provides:
  - "generate_arbitrary_shader() for configurable HLSL/ShaderLab shaders (SHDR-01)"
  - "generate_renderer_feature() for URP ScriptableRendererFeature with RenderGraph API (SHDR-02)"
  - "43 unit tests covering shader and renderer feature generation"
affects: [10-c-programming-framework, unity-shader-tool]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Configurable shader builder with property-to-CBUFFER auto-mapping"
    - "RenderGraph API pattern: RecordRenderGraph with blit+copy-back for fullscreen effects"
    - "Sanitization of shader names and C# identifiers for safe template output"

key-files:
  created:
    - "Tools/mcp-toolkit/tests/test_shader_templates_v2.py"
  modified:
    - "Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/shader_templates.py"

key-decisions:
  - "Texture property defaults use literal {} not f-string escaped {{}} since values are substituted as variables"
  - "Renderer feature generates two classes in one file: Feature + Pass, matching URP convention"
  - "Property-to-HLSL type mapping centralised in _hlsl_type_for_property helper"

patterns-established:
  - "_build_property_line: maps property dicts to ShaderLab Properties syntax"
  - "_build_pass: generates complete HLSL Pass block with structs, CBUFFER, and vert/frag functions"
  - "Renderer feature template: Create() -> material lifecycle, AddRenderPasses() -> Game camera guard, RecordRenderGraph() -> blit pattern"

requirements-completed: [SHDR-01, SHDR-02]

# Metrics
duration: 9min
completed: 2026-03-20
---

# Phase 10 Plan 02: Shader Templates v2 Summary

**Configurable HLSL/ShaderLab shader builder and URP 17 ScriptableRendererFeature generator with RenderGraph API, extending shader_templates.py with 2 new exports and 43 unit tests**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-20T09:10:10Z
- **Completed:** 2026-03-20T09:19:29Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extended shader_templates.py with generate_arbitrary_shader() supporting configurable properties, render types (Opaque/Transparent/TransparentCutout), custom vertex/fragment code, two-pass rendering, extra pragmas and includes
- Added generate_renderer_feature() producing ScriptableRendererFeature + ScriptableRenderPass using modern RenderGraph API (RecordRenderGraph), not legacy Execute()
- Created 43 unit tests across 3 test classes validating shader structure, C# output, brace balancing, and regression on all 7 original shaders
- Full test suite: 3,124 passed, 0 failures

## Task Commits

Each task was committed atomically:

1. **Task 1: Add generate_arbitrary_shader and generate_renderer_feature** - `7cfef2e` (feat)
2. **Task 2: Create unit tests for SHDR-01 and SHDR-02** - `6105bc2` (test)

## Files Created/Modified
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/shader_templates.py` - Extended with 2 new generators (generate_arbitrary_shader, generate_renderer_feature), helper functions (_build_property_line, _hlsl_type_for_property, _sanitize_shader_name, _sanitize_cs_identifier), and render type defaults dict
- `Tools/mcp-toolkit/tests/test_shader_templates_v2.py` - 43 unit tests across TestArbitraryShader (21), TestRendererFeature (20), TestExistingShadersNotBroken (2)

## Decisions Made
- Texture property defaults use `"white" {}` (not `"white" {{}}`) since values are substituted as f-string variables and NOT re-interpreted for escaping
- Renderer feature generates Feature + Pass in a single file, matching URP convention where the pass class is tightly coupled to the feature
- CBUFFER variables auto-generated from property list with correct HLSL type mapping (Color/Vector -> float4, Float/Range -> float, Texture -> TEXTURE2D + SAMPLER + _ST)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed texture property default f-string escaping**
- **Found during:** Task 2 (test_texture_property)
- **Issue:** `_build_property_line` used `'"white" {{}}'` as default for 2D texture properties, but since this value is substituted via f-string variable interpolation, the `{{` was NOT interpreted as f-string escape and appeared literally as `{{}}` in output
- **Fix:** Changed to `'"white" {}'` which is correctly passed through as `"white" {}` in the final output
- **Files modified:** shader_templates.py
- **Verification:** test_texture_property passes, brace balance tests pass
- **Committed in:** `6105bc2` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for correct ShaderLab syntax output. No scope creep.

## Issues Encountered
None beyond the f-string escaping bug caught by tests.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- shader_templates.py now has 9 exports (7 original + 2 new), ready for unity_shader compound tool integration in Plan 03/04
- Test coverage comprehensive with 43 new tests + 3,124 total suite passing
- No blockers for subsequent plans

## Self-Check: PASSED

- FOUND: shader_templates.py
- FOUND: test_shader_templates_v2.py
- FOUND: 10-02-SUMMARY.md
- FOUND: commit 7cfef2e
- FOUND: commit 6105bc2

---
*Phase: 10-c-programming-framework*
*Completed: 2026-03-20*
