# VeilBreakers GameDev Toolkit

## What This Is

Three custom MCP (Model Context Protocol) servers that transform Claude into a complete AAA game development team. Covers every discipline: 3D art, technical art, animation, environment art, VFX, audio, UI/UX, gameplay programming, QA, and build engineering. Built specifically for VeilBreakers 3D (Unity + Blender pipeline) but architecturally generic enough for any game project.

## Core Value

Every tool returns structured validation data and visual proof so Claude never works blind. The difference between "execute Python and hope" and "validated, previewed, verified at every step."

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Token-efficient compound tool architecture (26 tools, not 200+)
- [ ] Blender socket bridge addon with command dispatch
- [ ] Visual feedback system (screenshots, contact sheets, turntables, comparisons)
- [ ] Mesh topology analysis with A-F grading
- [ ] Surgical mesh editing (select by material/vertex group, sculpt, boolean, extrude)
- [ ] Surgical texture editing (mask region, AI inpaint, recolor, fix seams, wear maps)
- [ ] 10 creature rig templates (humanoid through amorphous) via Rigify
- [ ] Facial rigging system with monster-specific expressions
- [ ] Spring/jiggle bone system for secondary motion (hair, capes, tails)
- [ ] Shape keys for expressions and damage states
- [ ] Ragdoll auto-setup from existing rig
- [ ] Procedural animation generation (walk, fly, idle, attack, death, hit, spawn)
- [ ] Animation contact sheet preview system (every Nth frame, multiple angles)
- [ ] Procedural gait for all creature types (biped, quad, hexapod, arachnid, serpent)
- [ ] AI motion integration (HY-Motion, MotionGPT, Mixamo retargeting)
- [ ] Root motion + animation events for Unity
- [ ] Advanced terrain generation (caves, rivers, roads, cliffs, water bodies)
- [ ] AAA-quality building/castle/tower/bridge/town/dungeon generation
- [ ] Modular architecture kits (snap-together walls, floors, doors, windows)
- [ ] Ruins generation (damage existing structures realistically)
- [ ] Biome-aware vegetation scatter with slope/altitude rules
- [ ] Interior generation (furniture placement, wall decorations, lighting)
- [ ] Breakable prop variants and loot containers
- [ ] VFX pipeline: VFX Graph particles from descriptions
- [ ] Per-brand damage VFX (IRON sparks, VENOM drip, SURGE crackle, etc.)
- [ ] Corruption shader scaling with corruption percentage
- [ ] Environmental VFX (dust, fireflies, snow, rain, ash)
- [ ] Shader Graph creation (dissolve, force field, water, foliage, outline)
- [ ] Post-processing setup (bloom, color grading, vignette, AO, DOF)
- [ ] Screen effects (shake, damage vignette, heal glow, poison overlay)
- [ ] Hero/monster ability VFX with full animation integration
- [ ] Audio SFX generation from descriptions (AI-powered)
- [ ] Music loop generation (combat, exploration, boss, town)
- [ ] Voice line synthesis for NPCs/monsters
- [ ] Ambient soundscape generation per biome
- [ ] Footstep system (surface-material-aware)
- [ ] Adaptive music layers (add/remove based on game state)
- [ ] Audio zones (reverb, spatial, music triggers)
- [ ] Unity Audio Mixer + Manager with pooling
- [ ] UI screen generation (UXML + USS from descriptions)
- [ ] UI layout validation (overlaps, zero-size, overflow, contrast)
- [ ] Responsive testing at multiple resolutions
- [ ] Gemini visual review integration at all visual checkpoints
- [ ] Mob AI controller generation (patrol, aggro, combat, flee)
- [ ] NavMesh automation with NavMesh Links
- [ ] Behavior tree scaffolding
- [ ] Spawn system generation
- [ ] Combat ability prefab creation (animation + VFX + hitbox + damage + sound)
- [ ] Projectile systems with trajectory and trail VFX
- [ ] Tripo3D API integration for AI 3D generation
- [ ] Ubisoft CHORD integration for PBR texture generation (open source)
- [ ] Gaea CLI integration for professional terrain
- [ ] PyMeshLab mesh processing (analysis, repair, decimation, LOD)
- [ ] xatlas UV unwrapping automation
- [ ] Real-ESRGAN texture upscaling
- [ ] Unity-optimized FBX export with validation
- [ ] Auto LOD chain generation
- [ ] Performance profiling automation
- [ ] Lightmap and occlusion culling baking
- [ ] Build pipeline automation with size reports
- [ ] Asset audit (unused assets, oversized textures)
- [ ] Visual regression testing (screenshot comparison)
- [ ] Concept art generation from text descriptions
- [ ] Color palette generation
- [ ] Silhouette readability testing

### Out of Scope

- Live operations / analytics — not needed during development
- Mobile platform optimization — PC-first, mobile later
- Multiplayer/networking tools — VeilBreakers is single-player
- Custom game engine — Unity is the target, not building an engine
- Houdini integration — too expensive, Blender Geometry Nodes covers procedural needs

## Context

**Parent project**: VeilBreakers 3D — AAA-quality 3D monster RPG
- Unity (UI Toolkit, URP)
- 10 combat brands (IRON, SAVAGE, SURGE, VENOM, DREAD, LEECH, GRACE, MEND, RUIN, VOID)
- 4 hero paths (IRONBOUND, FANGBORN, VOIDTOUCHED, UNCHAINED)
- Corruption system (0-100%)
- Synergy tiers (FULL/PARTIAL/NEUTRAL/ANTI)
- User has Tripo3D subscription for character/monster model generation

**Triggering problem**: Blender rigging took 72 hours and was still broken. Claude operates blind — can't see what it creates, can't verify quality, can't do surgical edits. Token overhead from MCP tools wastes context window.

**Existing tools**: blender-mcp (basic), mcp-unity (basic), Gemini CLI, Serena, sequential-thinking, memory-graph, GitHub MCP

**Tech stack**: Python (FastMCP 3.0) for Blender + asset pipeline servers, C# + Node.js for Unity enhanced server. 34 external tools/APIs identified for integration.

**Multi-AI approach**: Claude handles code/architecture/execution. Gemini handles visual review/art direction. This is a core design principle — Gemini screenshots are Claude's "eyes."

## Constraints

- **Token efficiency**: Compound tool pattern mandatory. 26 tools max, not 200+. ~5,200 tokens context overhead target.
- **Validation-first**: Every tool must return structured validation data. No blind execution.
- **Visual proof**: Every visual operation must return a screenshot, contact sheet, or comparison image.
- **Quality over speed**: AAA quality at every level — topology, textures, animation, VFX, audio, environments. No "bare bones" implementations.
- **Blender version**: 3.6+ (Rigify required)
- **Unity version**: 2022.3+ (UI Toolkit, URP)
- **Platform**: Windows 11 (user's development machine)
- **Error scanning**: Bug/error scans required between every phase before proceeding

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FastMCP 3.0 for Python servers | Decorator-based, 5x faster dev, handles validation/typing | — Pending |
| Compound action pattern (not individual tools) | 8x token reduction (~5,200 vs ~40,000 tokens) | — Pending |
| Rigify-based rig templates (not from-scratch) | Industry-proven, extensible via feature sets, covers creatures | — Pending |
| Contact sheet for animation preview | Lets Claude "see" motion in a single image instead of per-frame | — Pending |
| Gemini as visual reviewer | Leverages Gemini's vision model as art director eye Claude lacks | — Pending |
| 6-wave implementation order | Prioritizes visual feedback (Wave 1) which unblocks everything else | — Pending |
| Separate repo from VeilBreakers | Clean separation of concerns, reusable for other projects | — Pending |
| URP focus (not HDRP) | Unity 2026 strategy: URP is the future, HDRP entering maintenance | — Pending |

---
*Last updated: 2026-03-18 after initialization*
