# Codebase Concerns

**Analysis Date:** 2026-03-29

## Tech Debt

**Monolithic Procedural Generation Files:**
- Issue: The core procedural generation logic is contained in massive, monolithic files that violate styling and architecture rules.
- Files: 
  - `Tools/mcp-toolkit/blender_addon/handlers/procedural_meshes.py` (19,683 lines)
  - `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py` (7,236 lines)
  - `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` (4,382 lines)
- Impact: Makes debugging, testing, and modifying 3D asset generators nearly impossible without introducing regression. Some individual functions like `generate_harbor_dock_mesh` are over 500 lines long.
- Fix approach: Split the files into modular components based on domain (e.g., `weapons.py`, `architecture.py`, `nature.py`).

**Incomplete Asset Pipeline Server:**
- Issue: The external standalone `asset-pipeline` module contains multiple unhandled stubs returning "not_yet_implemented".
- Files: `asset-pipeline/server.py`
- Impact: Any MCP call attempting to trigger Gaea, CHORD, or the actual Tripo3D SDK will fail silently with a JSON error payload instead of executing the pipeline.
- Fix approach: Replace the "TODO" stubs with proper client integrations or remove them if they are handled elsewhere in `veilbreakers_mcp/shared/`.

## Known Bugs

**Swallowed Exceptions in Blender Handlers:**
- Symptoms: Procedural operations (worldbuilding, environment scattering, building generation) fail silently when encountering edge cases, falling back to primitive geometry or ignoring the step entirely without alerting the user.
- Files: 
  - `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding.py` (Lines 5396, 5413, 5437)
  - `Tools/mcp-toolkit/blender_addon/handlers/_building_grammar.py` (Line 1049)
  - `Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py` (Line 1025)
  - `Tools/mcp-toolkit/blender_addon/handlers/worldbuilding_layout.py` (Lines 625, 712)
  - `Tools/mcp-toolkit/blender_addon/handlers/environment.py` (Lines 827, 1079, 1291, 1311, 1366)
- Trigger: Missing UV coordinates, missing materials, or failed boolean operations during procedural generation.
- Workaround: None. Errors are completely swallowed using `except Exception: pass`.

## Security Considerations

**Global State Mutation:**
- Risk: Cross-contamination of data between concurrent tool calls. Multiple handlers modify global variables like `_connection`, `_server`, and parsing state.
- Files: 
  - `Tools/mcp-toolkit/blender_addon/__init__.py`
  - `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py`
  - `Tools/mcp-toolkit/src/veilbreakers_mcp/_ast_analyzer.py`
- Current mitigation: None.
- Recommendations: Encapsulate state within class instances or use context managers for scoped variables.

## Performance Bottlenecks

**Uncached Regex in Hot Loops:**
- Problem: Regular expressions are compiled on the fly inside loops processing large source files (detected previously but prevalent).
- Files: `Tools/mcp-toolkit/src/veilbreakers_mcp/_rules_csharp.py`
- Cause: Repeated `re.search` inside `for` loops.
- Improvement path: Extract regex compilation to the module level.

## Fragile Areas

**Procedural Meshes Empty Returns:**
- Files: `Tools/mcp-toolkit/blender_addon/handlers/procedural_meshes.py` (Lines 95, 153)
- Why fragile: Some functions silently return empty lists `[]` when they should return vertices and faces, leading to invisible objects or missing geometry down the pipeline.
- Safe modification: Implement strict type hints and validation that all procedural generation methods return a valid `(verts, faces)` tuple.
- Test coverage: Zero coverage for edge cases in procedural meshes.

## Scaling Limits

**Blender Handler Memory Constraints:**
- Current capacity: Unknown, but monolithic scripts will cause huge memory overhead inside Blender's Python runtime.
- Limit: Complex city generation loops (`settlement_generator.py`) will eventually OOM or hang the TCP server.
- Scaling path: Implement async generation chunks or offload heavy calculation to a separate C++ module.

## Dependencies at Risk

**Missing External CLI Tools:**
- Risk: The `asset-pipeline` relies on `realesrgan-ncnn-vulkan`, `pymeshlab`, `xatlas`, and `tripo3d`.
- Impact: If these dependencies are not installed in the system PATH or Python environment, the tools fail with "module not found" errors instead of gracefully degrading.
- Migration plan: Implement dependency checks on startup and provide automatic installation scripts.

## Missing Critical Features

**Full Codebase Scan Gap:**
- Problem: The automated `vb_code_reviewer.py` scan documented in `FULL_SCAN_AND_FIXES_SUMMARY.md` completely skipped the `blender_addon/handlers` directory. It only scanned the MCP orchestrator side.
- Blocks: We have no automated tracking of heuristic, syntactic, or semantic errors inside the 50,000+ lines of Blender 3D procedural generation code.

## Test Coverage Gaps

**Blender Addon Handlers:**
- What's not tested: All procedural mesh generation, terrain chunking, and settlement grammar logic.
- Files: `Tools/mcp-toolkit/blender_addon/handlers/*.py`
- Risk: High chance of regressions when modifying the monolithic files since they are completely untested outside of manual visual verification.
- Priority: High. Need a headless Blender test suite.
