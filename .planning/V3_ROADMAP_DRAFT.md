# v3.0 Roadmap Draft — AAA Mesh Quality + Missing Systems

**Goal:** Close ALL remaining 3D modeling gaps + add ZBrush-level detail, FromSoft animation feel, Wwise-level audio, and AAA UI polish. Move from 40% to 95% AAA coverage.

## Phase 18: Procedural Mesh Integration + Terrain Depth
**Goal:** Wire 127 procedural meshes into worldbuilding/environment placement + add cliff/cave/terrain features
- Wire procedural_meshes.py into blender_worldbuilding handlers (buildings use real furniture, dungeons use real props)
- Wire into blender_environment (scatter uses real rocks/trees, not primitives)
- Add cliff face generator (vertical rock wall geometry beyond heightmap)
- Add cave entrance transition meshes (terrain-to-cave seamless geometry)
- Add multi-biome terrain transitions (forest→swamp→mountain blend zones)
- Add waterfall/cascade geometry
- Add bridge spanning generation (detect rivers/chasms, auto-bridge)
- Low-poly LOD variants for all mesh generators (performance budgets)

## Phase 19: Character Excellence
**Goal:** ZBrush-level character modeling workflow for hero and boss characters
- Body proportion validation system (hero=1.8m, boss=3-6m, NPC=1.7m, with enforced ratios)
- Hair card mesh generation (strip-based hair cards with UV layout for alpha textures)
- Face topology validation (edge loop detection around eyes/mouth/nose for proper deformation)
- Character LOD-aware retopology (preserve face detail, reduce body/extremities)
- Armor seam-hiding overlap rings (prevent visible gaps at split points)
- Hand/foot detail enforcement (finger separation, toe topology)
- Skin weight preparation checker (edge flow follows joint directions)
- Multires sculpting support (subdivision levels for detail work)

## Phase 20: Advanced Animation + FromSoft Feel
**Goal:** Hand-keyed combat timing, motion matching, and cinematic quality animation
- Combat timing system (anticipation frames, active frames, recovery frames — configurable per attack)
- Animation event injection (add hit/VFX/sound events at specific keyframes)
- Motion matching preparation (tag clips with features for runtime motion matching)
- Blend tree generation (directional movement, speed blending)
- Additive animation layers (damage reactions on top of locomotion)
- Root motion refinement (smooth curves, prevent drift)
- AI motion generation implementation (finish TODO stub — integrate with HunyuanVideo/MotionGPT)
- Cinematic animation tools (camera cuts, character staging, lip sync preparation)

## Phase 21: Audio Middleware Integration
**Goal:** Wwise/FMOD-level audio architecture without the middleware cost
- Spatial audio system (3D sound propagation, occlusion, HRTF)
- Layered sound design tools (combine multiple audio clips into complex sounds)
- Audio event graph (trigger chains: impact → reverb tail → debris scatter)
- Dynamic music system (horizontal re-sequencing, vertical layering, stingers)
- Dialogue system audio (VO pipeline with lip sync markers, emotion tags)
- Reverb zone authoring (convolution reverb from room geometry)
- Sound propagation through portals/doors (realistic attenuation between rooms)
- Audio LOD (reduce quality/channels at distance)

## Phase 22: AAA UI/UX Visual Polish
**Goal:** Hand-crafted dark fantasy UI that rivals BG3/Elden Ring
- Procedural UI frame generation (ornate borders, rune decorations, weathered edges)
- Icon generation pipeline (3D render → stylized 2D icon with background/border)
- Custom cursor generation (dark fantasy themed cursors per context)
- UI animation presets library (expand PrimeTween sequences for dark fantasy feel)
- Tooltip system with rich content (item stats, lore text, comparison)
- Radial menu generation (ability wheels, quick-select)
- Notification/toast system (quest updates, item pickups, achievements)
- Loading screen generation (tips, lore, concept art display)

## Phase 23: VFX Mastery
**Goal:** Particle systems and spell VFX that compete with Diablo 4/PoE
- Flipbook texture generation (animated sprite sheets for VFX)
- VFX Graph node composition (programmatic VFX Graph creation, not just parameters)
- Projectile VFX chains (spawn → travel → impact → aftermath sequence)
- Area-of-effect VFX (ground circles, expanding domes, cone blasts)
- Status effect VFX library (burning, poisoned, frozen, stunned, blessed, cursed per brand)
- Environmental VFX depth (volumetric fog, god rays, heat distortion, water caustics)
- Combat hit VFX (directional blood splatter, sparks, energy bursts per brand)
- Boss phase transition VFX (corruption wave, power surge, arena transformation)

## Phase 24: Production Pipeline
**Goal:** Close the loop on production workflows
- Compile error auto-recovery (detect, diagnose, fix, recompile cycle)
- Asset conflict detection (check for duplicate class names before writing)
- Multi-tool pipeline orchestration (character pipeline as single command)
- Build verification testing (smoke tests after every build)
- Performance regression detection (profile before/after changes)
- Art style consistency validator (cross-asset palette/roughness/detail checks)

## Summary

| Phase | Focus | Gaps Closed | Priority |
|-------|-------|-------------|----------|
| 18 | Mesh Integration + Terrain | ~15 | CRITICAL |
| 19 | Character Excellence | ~10 | CRITICAL |
| 20 | Animation + FromSoft Feel | ~8 | HIGH |
| 21 | Audio Middleware | ~6 | HIGH |
| 22 | UI/UX Visual Polish | ~8 | HIGH |
| 23 | VFX Mastery | ~8 | HIGH |
| 24 | Production Pipeline | ~5 | MEDIUM |

**Estimated total gaps closed: ~60 → bringing us from 40% to ~95% AAA coverage**
