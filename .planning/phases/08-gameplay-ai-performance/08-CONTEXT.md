# Phase 8: Gameplay AI & Performance - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers mob AI systems and performance optimization tools. Claude can generate mob controllers with state machines (patrol, aggro, chase, attack, flee), create combat ability prefabs, set up spawn systems, profile scene performance, and auto-optimize with LOD chains, lightmap baking, and asset auditing. This is the final integration layer that makes environments feel alive and the game run smoothly.

</domain>

<decisions>
## Implementation Decisions

### Mob AI System
- State machine based: patrol (waypoints), aggro (detection radius), chase, attack, flee (health threshold)
- Configurable parameters per mob type: detection range, attack range, leash distance, patrol speed, aggro speed
- Waypoint patrol with wait times at each point
- Aggro triggers on player proximity within detection radius
- Leash distance forces return to patrol if player gets too far

### Combat Abilities
- Ability prefabs combine: animation trigger + VFX prefab + hitbox collider + damage data + sound effect
- Projectile systems: velocity, trajectory (straight/arc/homing), trail VFX, impact VFX
- Cooldown system with ability queuing

### Spawn System
- Spawn point components with: max count, respawn timer, area bounds, conditions
- Wave-based spawning with configurable wave delays
- Spawn conditions: time of day, player proximity, quest state

### Performance Profiling
- Scene profiler reports: frame time, draw calls, batches, triangle count, memory usage
- Actionable recommendations based on threshold analysis
- Before/after comparison for optimization verification

### Auto-Optimization
- LOD chain generation (reuses existing pipeline_generate_lods)
- Lightmap baking with configurable quality settings
- Asset audit: unused assets, oversized textures, duplicate materials
- Occlusion culling setup

### Claude's Discretion
All implementation choices are at Claude's discretion — autonomous execution mode.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `unity_server.py` - Unity MCP server with 5 compound tools
- `shared/unity_templates/` - C# template generation pattern
- `blender_addon/handlers/pipeline_lod.py` - LOD generation
- `shared/pipeline_runner.py` - Batch processing pipeline

### Established Patterns
- C# template generation with f-string interpolation
- Compound MCP tools with Literal action params
- Pure-logic extraction for testable algorithms

### Integration Points
- Add `unity_gameplay` and `unity_performance` compound tools to unity_server.py
- C# templates written to Unity project via _write_to_unity helper

</code_context>

<specifics>
## Specific Ideas

- VeilBreakers mobs: various creature types with different AI behaviors
- Dark fantasy combat: melee + ranged + area-of-effect abilities
- Performance targets: 60fps on mid-range hardware

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
