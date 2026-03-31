# Phase 32: Building System - Context

**Gathered:** 2026-03-31
**Status:** Ready for planning
**Mode:** Auto-generated (discuss skipped via workflow.skip_discuss)

<domain>
## Phase Boundary

Building generation uses CGA-style split grammar for facade composition, producing architecturally varied structures with proper roofs, window/door cutouts, and modular kit pieces that snap on a consistent grid -- no building is a box with texture.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — discuss phase was skipped per user setting. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

## Existing Systems (from 30-RESEARCH.md)
- Building grammar: `_building_grammar.py` — evaluate_building_grammar() produces BuildingSpec with geometry ops. ALL detail ops (gargoyles, buttresses) are 0.5m cubes
- Building quality: `building_quality.py` — has AAA geometry (stone block grids, arch curves, voussoir blocks, shingle rows) but NOT wired into grammar
- Modular kit: `modular_building_kit.py` — 175 piece variants, 5 styles, _cut_opening() for windows/doors
- Worldbuilding: `worldbuilding.py` — VB_BUILDING_PRESETS (14 types), procedural materials assignment

Key techniques from research:
- CGA split grammar: footprint → extrude → comp(faces) → split(y, floors) → split(x, bays) → fill rules
- Straight skeleton roofs: bpypolyskel for hip/gable/mansard from arbitrary footprints
- bmesh ops: extrude_face_region, subdivide_edges, bevel, bisect_plane, solidify, face_split

</code_context>

<specifics>
## Specific Ideas

No specific requirements — discuss phase skipped. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — discuss phase skipped.

</deferred>
