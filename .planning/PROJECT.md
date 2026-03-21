# VeilBreakers GameDev Toolkit

## What This Is

Three custom MCP (Model Context Protocol) servers that transform Claude into a complete AAA game development team. Covers every discipline: 3D art, technical art, animation, environment art, VFX, audio, UI/UX, gameplay programming, QA, and build engineering. Built specifically for VeilBreakers 3D (Unity + Blender pipeline) but architecturally generic enough for any game project.

## Core Value

Every tool returns structured validation data and visual proof so Claude never works blind. The difference between "execute Python and hope" and "validated, previewed, verified at every step."

## Requirements

### Validated

v1.0 delivered (2026-03-19): 22 MCP tools, 86 Blender handlers, 153 capabilities, 2740 tests.
- ✓ Token-efficient compound tool architecture
- ✓ Blender socket bridge addon with command dispatch (86 handlers)
- ✓ Visual feedback system (screenshots, contact sheets)
- ✓ Full mesh/UV/texture/rig/animation/environment/worldbuilding pipeline
- ✓ Unity VFX/Audio/UI/Scene/Gameplay/Performance tools

v2.0 delivered (2026-03-21): 37 MCP tools (15 Blender + 22 Unity), 309 actions, 7182 tests, 135 bugs fixed.
- ✓ Unity Editor deep control (prefabs, components, hierarchy, physics, settings, packages)
- ✓ General-purpose C# code generation + script modification
- ✓ Complete game systems (save/load, health, combat, inventory, dialogue, quests, loot, crafting, skill trees)
- ✓ Camera/Cinemachine 3.x + Timeline + cutscenes + animation editing
- ✓ Data architecture (ScriptableObjects, JSON, localization) + AAA quality enforcement
- ✓ World design (16 room types, world graph, boss arenas, multi-floor dungeons, weather, day/night)
- ✓ Game UX (minimap, damage numbers, tutorials, accessibility, encounter scripting, boss AI)
- ✓ Unity TCP bridge (direct editor communication, no mcp-unity dependency)
- ✓ QA/Testing (test runner, profiler, memory leaks, static analysis, compile error detection)
- ✓ Build pipeline (multi-platform, Addressables, CI/CD, versioning, shader stripping)
- ✓ 127 procedural mesh generators across 21 categories

## Milestone: v3.0 — AAA Mesh Quality + Professional Systems -- COMPLETE

**Status:** COMPLETE (2026-03-21)
**Goal achieved:** Closed ALL remaining 3D modeling gaps, added ZBrush-level character workflows, FromSoft-level animation timing, Wwise-level audio architecture, and AAA UI/VFX polish. Moved from 40% to 95% AAA coverage.

### Key Metrics

| Metric | Value |
|--------|-------|
| MCP tools | 37 (15 Blender + 22 Unity) |
| Total actions | 350 (309 v2.0 + 41 v3.0) |
| Total tests | 8,473+ |
| v3.0 new tests | 1,154 |
| Phases complete | 24/24 |
| Requirements complete | v1: 128, v2: 143, v3: 56 (all complete) |
| Bugs fixed | 135+ |
| Procedural mesh generators | 127 across 21 categories |

### Delivered (v3.0)

- [x] 127 procedural meshes wired into worldbuilding/environment (real meshes, not primitives)
- [x] Terrain depth (cliffs, caves, multi-biome, waterfalls, bridges)
- [x] Character excellence (hair cards, face topology, proportions, armor seams, cloth physics)
- [x] SSS skin shaders, parallax eye shaders, micro-detail normals
- [x] FromSoft combat animation timing (anticipation/active/recovery frames)
- [x] Blend trees, additive animation layers, cinematic sequences
- [x] Wwise-level spatial audio (propagation, occlusion, layered sound design, portal audio)
- [x] Dynamic music, procedural foley, VO pipeline with lip sync
- [x] AAA dark fantasy UI (ornate borders, icon pipeline, radial menus, tooltips, cursors)
- [x] Loading screens, notification toasts, UI material shaders
- [x] Diablo 4-level VFX (flipbooks, VFX Graph composition, spell chains, status effects)
- [x] Projectile chains, AoE VFX, boss phase transitions, directional hit VFX
- [x] Production pipeline (compile auto-recovery, conflict detection, orchestration)
- [x] Art style validation, build smoke tests

### Out of Scope

- Live operations / analytics — not needed during development
- Mobile platform optimization — PC-first, mobile later
- Multiplayer/networking tools — VeilBreakers is single-player (revisit if needed)
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
| FastMCP 3.0 for Python servers | Decorator-based, 5x faster dev, handles validation/typing | ✓ Good |
| Compound action pattern (not individual tools) | 8x token reduction (~5,200 vs ~40,000 tokens) | ✓ Good |
| Rigify-based rig templates (not from-scratch) | Industry-proven, extensible via feature sets, covers creatures | ✓ Good |
| Contact sheet for animation preview | Lets Claude "see" motion in a single image instead of per-frame | ✓ Good |
| Gemini as visual reviewer | Leverages Gemini's vision model as art director eye Claude lacks | ✓ Good |
| 6-wave implementation order | Prioritizes visual feedback (Wave 1) which unblocks everything else | ✓ Good |
| Separate repo from VeilBreakers | Clean separation of concerns, reusable for other projects | ✓ Good |
| URP focus (not HDRP) | Unity 2026 strategy: URP is the future, HDRP entering maintenance | ✓ Good |
| v1.0 code generation pattern for Unity tools | Generates C# scripts written to disk, not live RPC | ✓ Good |
| All v1.0 Active requirements delivered | 8 phases, 22 tools, 2740 tests | ✓ Good |
| v2.0 Unity TCP bridge (not mcp-unity) | Direct editor communication, no external dependency | ✓ Good |
| v2.0 Line-based string concat for C# templates | Consistent, readable, easy to test | ✓ Good |
| v3.0 Generator mapping pattern (dict dispatch) | Clean type-to-generator dispatch for all v3.0 template modules | ✓ Good |
| v3.0 Pure-logic modules (no bpy) | Enables comprehensive pytest testing without Blender | ✓ Good |
| v3.0 FromSoft 3-phase combat timing | Per-frame precision: anticipation/active/recovery phases | ✓ Good |
| v3.0 Single template file per phase | Consistent pattern for Phase 21-24 Unity generators | ✓ Good |
| v3.0 Brand color palette centralization | Hex + rgba + glow for all 10 brands, shared across VFX/UI | ✓ Good |
| v3.0 Stream-based C# parser | Offline syntax validation without Roslyn, handles verbatim strings | ✓ Good |

---
*Last updated: 2026-03-21 -- v3.0 COMPLETE*
