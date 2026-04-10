# Phase 39: Pipeline & Systemic Fixes - Context

**Gathered:** 2026-04-04
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Eliminate every systemic pipeline bug so downstream phases build on clean foundation. Fix pipeline dispatch routing, Z=0 hardcoded placements, deprecated Blender 5.0 API calls, Y-axis vertical bugs, square-terrain assumptions, and create shared utilities (smootherstep, safe_place_object). Wire compose_world_map smart planner into compose_map.

Requirements: PIPE-01 through PIPE-08, TEST-01, TEST-04

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use V9_MASTER_FINDINGS.md (sections 1-2, 16.10, 19.1) as the authoritative source for every bug location and fix specification. Follow ROADMAP phase goal, success criteria, and codebase conventions.

Key references for exact line numbers and fix details:
- V9_MASTER_FINDINGS.md Section 1: Pipeline Architecture (dispatch bugs, smart planner)
- V9_MASTER_FINDINGS.md Section 2: Codebase-Wide Systemic Bugs (147+ instances with file:line)
- V9_MASTER_FINDINGS.md Section 16.10: Additional Code Bugs
- V9_MASTER_FINDINGS.md Section 19.1: Foundational Rules (smootherstep, safe_place_object utilities)

</decisions>

<code_context>
## Existing Code Insights

Codebase context will be gathered during plan-phase research.

Key files to investigate:
- Tools/mcp-toolkit/blender_addon/handlers/ — all handler files
- Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py — compose_map, _LOC_HANDLERS
- Tools/mcp-toolkit/blender_addon/__init__.py — COMMAND_HANDLERS dispatch

</code_context>

<specifics>
## Specific Ideas

- Create smootherstep(t) = t * t * (3 - 2 * t) as shared utility function
- Create safe_place_object(x, y, terrain_name) wrapper: _sample_scene_height() + water exclusion + bounds check
- These two utilities replace 42 Z=0 hardcodings and 35 linear interpolation sites
- Blender 5.0 API: group.inputs.new() → group.interface.new_socket(), ShaderNodeTexMusgrave → Noise Texture, cap_fill → fill_type

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase, all items are in scope.

</deferred>

---

*Phase: 39-pipeline-systemic-fixes*
*Context gathered: 2026-04-04 via autonomous infrastructure detection*
