# Phase 7: VFX, Audio, UI & Unity Scene - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers Unity-side tools for VFX, audio, UI, and scene setup. Claude can generate VFX Graph particles from text, create per-brand damage VFX, set up audio with AI-generated SFX/music/voice, build UI screens from descriptions, import scenes with terrain/lighting/NavMesh, and perform visual quality review. This is the Unity integration layer that connects all Blender-side assets into playable game scenes.

IMPORTANT: This phase also includes a Unity auto-recompile/refresh capability so Claude can trigger script recompilation and play mode without human interaction.

</domain>

<decisions>
## Implementation Decisions

### VFX System
- VFX descriptions are parsed into VFX Graph component parameters (rate, lifetime, size, color, shape)
- Per-brand VFX variants: IRON (sparks, metal), VENOM (drip, acid green), SURGE (crackle, electric blue)
- Corruption shader scales visual corruption percentage on materials
- Environmental VFX: dust, fireflies, snow, rain, ash as reusable prefab templates
- Shader Graph templates: dissolve, force field, water, foliage, outline

### Audio System
- AI SFX generation via ElevenLabs or stub (sound description -> wav file)
- Music loop generation: combat, exploration, boss, town themes
- Voice line synthesis for NPCs/monsters
- Ambient soundscape per biome (forest, cave, town, dungeon)
- Footstep system maps surface material to sound bank
- Adaptive music layers add/remove tracks based on game state
- Unity Audio Mixer setup with group routing and audio pool manager

### UI System
- UI screens generated from text descriptions as UXML + USS (Unity UI Toolkit)
- Layout validation: overlap detection, zero-size elements, overflow, WCAG contrast
- Responsive testing at 5 standard resolutions (1920x1080, 2560x1440, 3840x2160, 1280x720, 800x600)
- Post-processing: bloom, color grading, vignette, AO, DOF
- Screen effects: camera shake, damage vignette, heal glow, poison overlay

### Unity Scene Setup
- Scene import: terrain heightmaps, object scatter, lighting/fog/post-processing
- NavMesh baking with configurable agent settings
- Animator Controller setup with blend trees
- Screenshot comparison for visual regression detection

### Unity Auto-Recompile (User Requested)
- Tool to trigger AssetDatabase.Refresh() for script recompilation
- Enter/exit play mode programmatically
- Capture screenshots of game/scene view
- Read Unity console logs for errors/warnings
- This removes human-in-the-loop bottleneck

### Claude's Discretion
All implementation choices are at Claude's discretion — autonomous execution mode.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.mcp.json` has mcp-unity server entry for Unity communication
- `blender_server.py` pattern for compound MCP tools
- Existing texture/material system for shader parameter setup
- Pipeline runner for batch operations

### Established Patterns
- Compound MCP tools with Literal action params
- Pure-logic extraction for testable functions
- JSON-based configuration and template systems

### Integration Points
- Unity MCP server (mcp-unity) for C# script generation and scene manipulation
- New MCP tools for VFX, audio, UI, scene setup
- Integration with existing Blender export pipeline

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers brand system: IRON, VENOM, SURGE, VOID, BLAZE damage types
- Dark fantasy/horror aesthetic for all VFX and UI
- Unity UI Toolkit (UXML/USS) over legacy UGUI

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
