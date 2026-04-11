# Repo Audit — Terrain/Quality/Nodes/Texturing/Blender Agent

Date: 2026-04-10 (UTC)

## Scope
- Terrain generation branch behavior and pass orchestration
- Quality verification pipelines
- Node generation/completion/merging surfaces (geometry + worldbuilding shell merge flows)
- Texturing pipeline and texture safety
- Agent-facing Blender manipulation/toolchain contract behavior

## Deep-dive method (terrain-focused vs. whole repo)
1. Ran static reviewer over `blender_addon/handlers` (strict) and `src/veilbreakers_mcp` (production), then compared terrain-specific findings against whole-repo findings.
2. Ran targeted pytest suites covering terrain, worldbuilding, geometry-node surfaces, texturing, quality gates, and orchestration integration.
3. Re-ran static reviewer after fixes to verify high-severity issue burn-down.

## What was executed
- `asset_pipeline` equivalent inspection attempt via `handle_inspect_external_toolchain({})` in headless Python import path.
- Targeted high-signal test suites across terrain/worldbuilding/geometry-node/texturing/quality.
- Static compile pass (`compileall`) over MCP server and Blender handlers.
- Heuristic static bug scan via `vb_python_reviewer.py` on handlers and src.

## Verification summary
- Terrain + worldbuilding + geometry node + texture + quality tests selected for this audit all passed.
  - Batch A: 947 tests passed.
  - Batch B: 281 tests passed.
  - Batch C: 50 tests passed.
  - Batch D (regression for fixes): 567 tests passed.
  - Batch E (terrain/worldbuilding regressions): 77 tests passed.
- Python compile checks passed for relevant source trees.

## Deep-dive findings delta (before fixes)

### Terrain-focused branch surfaces
- Terrain-specific high findings were concentrated in:
  - `terrain_unity_export_contracts.py` (assert-based invariants)
  - `terrain_checkpoints_ext.py` (reviewer-reported late-binding pattern)

### Whole-repo high findings
- Additional high findings outside terrain-core included:
  - Dynamic `exec` in texture detail setup (`texture.py`)
  - Reviewer self-flag in `vb_code_reviewer.py`
  - Reviewer late-binding flags in worldbuilding/rigging paths

## Fixes implemented in this pass

### 1) Removed assert-based invariants in terrain export contracts
- Replaced cardinality `assert` checks with explicit runtime `RuntimeError` guards so checks are preserved in optimized Python runs.

### 2) Removed dynamic code execution in texture detail apply path
- `texture_apply_detail` no longer executes generated code in-process.
- Handler now returns deterministic generated code payload and explicitly marks `manual_apply_required=True`.

### 3) Added headless fallback contract for toolchain inspection
- `handle_inspect_external_toolchain` now returns `status=success` with deterministic fallback contract when `bpy` is unavailable.
- Includes `headless_fallback=True` and runtime availability markers.

### 4) Added compose_interior checkpoint parity
- Added checkpoint load/save/restart compatibility flow for `compose_interior` using shared pipeline checkpoint utilities.
- Includes `resumed_from_checkpoint`, `checkpoint_dir`, and periodic checkpoint writes across major interior steps.

### 5) Cleared reviewer high-severity late-binding hits
- Refactored flagged lambda patterns in terrain/worldbuilding/rigging/reviewer code paths.

## Post-fix status
- `vb_python_reviewer.py` high-severity scan:
  - handlers: **0 HIGH**
  - src: **0 HIGH**

## Positive checks (still solid)
- Toolchain contract preset encodes Unity-ready terrain sequence with `prepare_heightmap_raw_u16` before `validation_full`.
- Terrain pass registration and master registrar coverage remain strong via passing suites.
- Node/worldbuilding structural merge surfaces exercised in regression tests.

## Suggested next hardening backlog (remaining medium debt)
1. Tighten broad `except Exception` boundaries in orchestration paths.
2. Convert additional advisory medium findings where practical (false-positive pruning in reviewer rules).
3. Add explicit integration tests for compose_interior checkpoint resume/restart semantics.
