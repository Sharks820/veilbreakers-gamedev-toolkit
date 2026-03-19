# Phase 4: Rigging - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a complete rigging pipeline for game creatures. Claude can analyze meshes, apply creature-specific rig templates, paint weights, test deformation, build facial rigs, add secondary motion physics, validate rigs, and set up ragdolls. All through Blender handlers dispatched via the existing MCP bridge.

</domain>

<decisions>
## Implementation Decisions

### Rig Templates & Architecture
- Use Rigify as the base for all 10 creature rig templates (humanoid, quadruped, bird, insect, serpent, floating, dragon, multi-armed, arachnid, amorphous)
- Each template is a Python function that generates Rigify metarig bone layout programmatically (not .blend template files)
- Custom rig builder allows mixing limb types from different templates
- All rig templates produce game-ready control rigs with DEF, MCH, and ORG bone layers

### Facial Rigging
- Facial rig uses bone-based controls (not shape key drivers) for jaw, lips, eyelids, eyebrows, cheeks
- Monster-specific expressions (snarl, hiss, roar) are predefined bone poses stored as pose library entries
- Shape keys are used for expression/damage states that morph mesh geometry (separate from bone-based facial rig)

### Weight Painting & Deformation
- Auto weight painting uses Blender's built-in "Automatic Weights" with heat diffusion
- Deformation testing at 8 standard poses: T-pose, A-pose, crouch, reach-up, twist-left, twist-right, extreme-bend, action-pose
- Contact sheet output for deformation test uses existing render_contact_sheet infrastructure

### Secondary Motion & Physics
- Spring/jiggle bones use Blender's rigid body constraints or bone constraints with damped track
- Apply to: tails, hair, capes, chains, ears, antennae, tentacles
- Settings are per-bone configurable (stiffness, damping, gravity)

### Validation & Ragdoll
- Rig validation checks: unweighted vertices, weight bleeding across bones, bone roll consistency, symmetry, constraint validity
- Ragdoll auto-setup generates box/capsule colliders per bone segment with hinge/cone joint limits
- Weight mirror uses Blender's built-in mirror with vertex group name pattern (L/R suffix)

### Claude's Discretion
All implementation choices are at Claude's discretion — autonomous execution mode.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `blender_addon/handlers/` - Existing handler pattern for all Blender commands
- `blender_addon/socket_server.py` - Queue+timer dispatch pattern
- `blender_addon/handlers/__init__.py` - COMMAND_HANDLERS registry (43 entries)
- `blender_server.py` - Compound MCP tool pattern with action Literal

### Established Patterns
- Handler functions: `handle_*(params: dict) -> dict`
- Compound tools: `@mcp.tool() async def blender_*(action: Literal[...], ...)`
- Visual verification: `_with_screenshot()` for mutations
- bmesh usage in handlers for mesh analysis (see mesh handlers, UV handlers)

### Integration Points
- New handlers register in `COMMAND_HANDLERS` dict in `handlers/__init__.py`
- New compound tool `blender_rig` adds to `blender_server.py`
- Deformation test uses existing `render_contact_sheet` handler

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers creatures include humanoid, quadruped, serpent, insect, dragon, floating, multi-armed, arachnid, amorphous types
- Monster facial expressions: snarl, hiss, roar (not standard human expressions)
- Game target is Unity — rigs must export cleanly to FBX with Unity-compatible bone hierarchy

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
