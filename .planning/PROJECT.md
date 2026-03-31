# VeilBreakers GameDev Toolkit

## What This Is

Three custom MCP (Model Context Protocol) servers that transform Claude into a complete AAA game development team. Covers every discipline: 3D art, technical art, animation, environment art, VFX, audio, UI/UX, gameplay programming, QA, and build engineering. Built specifically for VeilBreakers3D (Unity + Blender pipeline) but architecturally generic enough for any game project.

## Core Value

Every tool returns structured validation data and visual proof so Claude never works blind. The difference between "execute Python and hope" and "validated, previewed, verified at every step."

## Requirements

### Validated

v1.0 delivered (2026-03-19): 22 MCP tools, 86 Blender handlers, 153 capabilities, 2,740 tests.
- ✓ Token-efficient compound tool architecture
- ✓ Blender socket bridge addon with command dispatch (86 handlers)
- ✓ Visual feedback system (screenshots, contact sheets)
- ✓ Full mesh/UV/texture/rig/animation/environment/worldbuilding pipeline
- ✓ Unity VFX/Audio/UI/Scene/Gameplay/Performance tools

v2.0 delivered (2026-03-21): 37 MCP tools (15 Blender + 22 Unity), 309 actions, 7,182 tests, 135 bugs fixed.
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
- ✓ 267 procedural mesh generators across 21 categories

v3.0 delivered (2026-03-21): COMPLETE
- ✓ AAA Mesh Quality + Professional Systems (all 56 requirements, 8,473+ tests, 24 phases)

### Active
- [ ] **MESH-01**: AAA procedural 3D models (Skyrim/Fable quality) — no third-grade generation
- [ ] **MESH-02**: High-level textures — AAA quality, PBR complete
- [ ] **MESH-03**: Interior mapping and furnishing — complete interior systems
- [ ] **MESH-04**: Intelligent building design — storyline-aware, non-cookie-cutter architecture
- [ ] **MESH-05**: Terrain/building mesh integration — seamless terrain-city blending
- [ ] **MESH-06**: High-level geometry — clean edges, professional topology
- [ ] **MESH-07**: High-level architectural design — AAA structural quality
- [ ] **MESH-08**: City infrastructure mapping — roads, paths, shops
- [ ] **MESH-09**: Intelligent biome mapping — corruption-aware, logical distribution
- [ ] **MESH-10**: Effective biome meshing — meshes work together visually
- [ ] **MESH-11**: Performance-conscious environmental assets — no model spam, optimized
- [ ] **MESH-12**: Tripo pipeline utilization — small/medium/large assets, furnishing
- [ ] **MESH-13**: Starter town for testing — functional, gameplay-ready
- [ ] **MESH-14**: Auto-compact workflow — context management at 80%
- [ ] **MESH-15**: GLM memory stack persistence — save learnings
- [ ] **MESH-16**: Clean commit workflow — after every bug/error scan
- [ ] **PIPE-01**: Research AAA game techniques (Skyrim, Fable, Valhalla, open-world medieval)

### Out of Scope

- Live operations / analytics — not needed during development
- Mobile platform optimization — PC-first, mobile later
- Multiplayer/networking tools — VeilBreakers is single-player (revisit if needed)
- Custom game engine — Unity is target, not building an engine
- Houdini integration — too expensive, Blender Geometry Nodes covers procedural needs
- Third-grade model generation — EXPLICITLY OUT (user requirement)

## Current Milestone: v7.0 — AAA Procedural City Production (ACTIVE)

**Goal:** Transform VeilBreakers MCP Toolkit from placeholder-grade procedural generation to ultra-competitive AAA studio quality comparable to Skyrim/Fable/AC Valhalla. Build complete procedural city pipeline with walkable interiors, modular architecture, multi-biome terrain, intelligent prop placement, and AAA-quality environmental props. Implement visual-first AI workflow where every inch of generated geometry and material is inspectable without reimporting to Blender. No Hugging Face (8GB VRAM limit) — use Tripo pipeline exclusively. Deliver production-ready starter town for testing with full streaming, occlusion, and runtime systems.

**Target features:**
- AAA procedural 3D models — Skyrim/Fable/Valhalla benchmark quality
- High-level textures — AAA quality PBR textures
- Interior mapping and furnishing — Complete interior systems
- Intelligent building design — Storyline-aware, non-cookie-cutter architecture
- Terrain/building mesh integration — Seamless blending, no gaps
- High-level geometry — Clean edges, professional topology
- High-level architectural design — AAA structural quality
- City infrastructure mapping — Roads, paths, shops, complete mapping
- Intelligent biome mapping — Corruption-aware, logical distribution
- Effective biome meshing — Visual coherence across meshes
- Performance-conscious assets — No model spam, optimized
- Tripo pipeline utilization — Small/medium/large assets, furnishing upgrades
- Starter town for testing — Functional, gameplay-ready location
- Auto-compact workflow — Context management at 80%
- GLM memory persistence — Save learnings across sessions
- Clean commit workflow — After every bug/error scan
- Deep research — AAA game techniques, software use cases

## Context

**Parent project**: VeilBreakers3D — AAA-quality 3D monster RPG
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
- **Error scanning**: Bug/error scans required between every phase before proceeding.
- **Performance**: No model spam, optimize at creation, LOD strategy
- **Memory management**: Auto-compact at 80% context, GLM persistence
- **Commit discipline**: Clean commits after every scan

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FastMCP 3.0 for Python servers | Decorator-based, 5x faster dev, handles validation/typing | ✓ Good |
| Compound action pattern (not individual tools) | 8x token reduction (~5,200 vs ~40,000 tokens) | ✓ Good |
| Rigify-based rig templates (not from-scratch) | Industry-proven, extensible via feature sets | ✓ Good |
| Contact sheet for animation preview | Lets Claude "see" motion in a single image instead of per-frame | ✓ Good |
| Gemini as visual reviewer | Leverages Gemini's vision model as art director eye Claude lacks | ✓ Good |
| 6-wave implementation order | Prioritizes visual feedback (Wave 1) which unblocks everything else | ✓ Good |
| Separate repo from VeilBreakers | Clean separation of concerns, reusable for other projects | ✓ Good |
| URP focus (not HDRP) | Unity 2026 strategy: URP is now, HDRP entering maintenance | ✓ Good |
| v1.0 code generation pattern for Unity tools | Generates C# scripts written to disk, not live RPC | ✓ Good |
| v2.0 Unity TCP bridge (not mcp-unity) | Direct editor communication, no external dependency | ✓ Good |
| v2.0 Line-based string concat for C# templates | Consistent, readable, easy to test | ✓ Good |
| v3.0 Generator mapping pattern | Clean type-to-generator dispatch for all 267 procedural meshes | ✓ Good |
| v3.0 bpy-guarded bridge pattern | Pure-logic + try/import bpy in same module | ✓ Good |
| v3.0 Pure-logic character validation | Enables comprehensive pytest testing without Blender | ✓ Good |
| v3.0 GDC 2011 fast SSS approximation | Real-time skin rendering in URP | ✓ Good |
| v3.0 Region-weighted vertex importance | Character-aware LOD animation | ✓ Good |
| v3.0 Joint-spec dict pattern | 8 joint types for body part positioning | ✓ Good |
| v3.0 Cloth preset system | 5 presets with type-based defaults | ✓ Good |
| v3.0 MaterialPropertyBlock micro-details | Per-instance micro-detail normal compositing | ✓ Good |
| v3.0 FromSoft 3-phase combat timing | Anticipation/active/recovery with per-frame precision | ✓ Good |
| v3.0 Brand-specific VFX/sound parameters | All 10 VeilBreakers brands | ✓ Good |
| v3.0 Procedural AI motion fallback | Fallback when no API endpoint | ✓ Good |
| v3.0 requests library for HTTP API calls | Avoids urllib file:// vulnerability | ✓ Good |
| v3.0 Shot-based cinematic composition | Cumulative timing and transition blending | ✓ Good |
| v3.0 Dict return pattern for audio generators | script_path, content, next_steps | ✓ Good |
| v3.0 Runtime-only MonoBehaviours | Build compatibility, no UnityEditor imports | ✓ Good |
| v3.0 ScriptableObject data assets | Layered sounds, event chains, VO database | ✓ Good |
| v3.0 Multi-ray occlusion | 3 rays for accurate spatial audio | ✓ Good |
| v3.0 Coroutine-based sequencing | Event chains and music crossfades | ✓ Good |
| v3.0 Singleton DynamicMusic manager | DontDestroyOnLoad persistence | ✓ Good |
| v3.0 Priority-based VO queue | Interruption support, lip sync visemes | ✓ Good |
| v3.0 Single template for UIPOL generators | Consistent with Phase 21 pattern | ✓ Good |
| v3.0 PrimeTween with fallback | Schedule.Execute fallback for animation | ✓ Good |
| v3.0 USS generated alongside C# | Complete UI Toolkit setup | ✓ Good |
| v3.0 URP HLSL for UI shaders | Multi-effect toggle properties | ✓ Good |
| v3.0 Shared rarity color system | VB_COLORS + RARITY_COLORS constants | ✓ Good |
| v3.0 Single template for VFX3 generators | Consistent with Phase 21/22 pattern | ✓ Good |
| v3.0 Centralized brand color palette | Hex + rgba + glow for all 10 brands | ✓ Good |
| v3.0 Coroutine-based VFX lifecycle | Projectile chains, AoE, boss transitions | ✓ Good |
| v3.0 MaterialPropertyBlock runtime glow | No material cloning per-frame | ✓ Good |
| v3.0 Per-brand secondary effects | Unique visuals (SURGE LineRenderer arcs, etc.) | ✓ Good |
| v3.0 4-stage projectile chain | Spawn/trail/impact/aftermath pattern | ✓ Good |
| v3.0 3-stage boss transition | Phase intensity scaling, event callbacks | ✓ Good |
| v3.0 Single template for PROD generators | Consistent with Phase 21/22/23 pattern | ✓ Good |
| v3.0 Stream-based C# parser | Offline validation, handles verbatim/interpolated strings | ✓ Good |
| v3.0 5-class error taxonomy | Compile error auto-recovery (3 auto-fixable) | ✓ Good |
| v3.0 4 built-in pipeline definitions | Sequential dependency graph | ✓ Good |
| v3.0 HSV distance metric | Per-color tolerance for palette validation | ✓ Good |
| v4.0: Third-grade model generation EXCLUDED | Must reach AAA quality, no shortcuts | ✓ Good |
| v4.0: Research AAA game techniques | Deep dive into Skyrim/Fable/etc. | ✓ Good |
| v4.0: Performance-conscious assets | No model spam, optimized from creation | ✓ Good |
| v4.0: Auto-compact at 80% | Memory management to prevent bloat | ✓ Good |
| v4.0: GLM memory persistence | Save learnings across sessions | ✓ Good |
| v4.0: Clean commit workflow | After every bug/error scan | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30 — v4.0 initialized*
