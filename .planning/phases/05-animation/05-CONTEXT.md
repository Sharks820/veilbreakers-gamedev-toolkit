# Phase 5: Animation - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers a complete animation pipeline for game creatures. Claude can generate procedural walk/run/fly/idle cycles for any creature type, create combat/death/spawn animations, preview animations via contact sheets, add secondary motion physics, extract root motion, retarget AI-generated and Mixamo animations, and batch export as Unity animation clips.

</domain>

<decisions>
## Implementation Decisions

### Procedural Animation System
- Walk/run cycles are generated procedurally using keyframe math (sine waves for leg cycles, phase offsets per gait type)
- 5 gait types: biped, quadruped, hexapod, arachnid, serpent - each with unique foot placement patterns
- Fly/hover cycles use wing bone oscillation with adjustable frequency, amplitude, and glide ratio
- Idle animations use subtle breathing (chest/spine), weight shift, and secondary motion

### Combat & Action Animations
- Attack types: melee swing, thrust, slam, bite, claw, tail whip, wing buffet, breath attack
- Death, hit reaction (directional), and spawn animations generated from parametric descriptions
- Custom animation from text description maps to keyframe sequences on rig bones

### Animation Preview & Verification
- Contact sheet preview renders every Nth frame from multiple angles using existing render infrastructure
- Frame stepping and angle configuration match the viewport contact sheet pattern

### Motion Integration
- AI motion generation stub for HY-Motion/MotionGPT (API integration placeholder)
- Mixamo animation retargeting maps standard Mixamo bone names to custom rig bone names
- Retargeting uses constraint-based approach matching Phase 4 rig retargeting pattern

### Export & Unity Integration
- Root motion extraction separates hip/root translation from animation curves
- Animation events mark contact frames (footsteps, hit impacts) as NLA markers
- Batch export produces separate FBX files per animation clip with Unity-compatible naming

### Claude's Discretion
All implementation choices are at Claude's discretion — autonomous execution mode.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `blender_addon/handlers/rigging_templates.py` - Rig template bone definitions (DEF bone names for keyframing)
- `blender_addon/handlers/rigging_weights.py` - DEFORMATION_POSES constant (8 standard poses)
- `blender_addon/handlers/viewport.py` - render_contact_sheet handler
- `blender_server.py` - Compound MCP tool pattern (12 tools currently)

### Established Patterns
- Handler functions: `handle_*(params: dict) -> dict`
- Pure-logic extraction for testable math functions
- Compound tools with Literal action params
- Visual verification via _with_screenshot()

### Integration Points
- New handlers register in COMMAND_HANDLERS dict
- New compound tool `blender_animation` adds to blender_server.py
- Animation preview reuses existing contact sheet infrastructure

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers creatures: humanoid, quadruped, serpent, insect, dragon, floating, multi-armed, arachnid, amorphous
- Combat-focused game - attack and death animations are critical
- Unity target with Animator Controller integration

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
