# Phase 48: Starter City Generation & Final Verification - Research

**Researched:** 2026-04-04
**Domain:** Full world generation pipeline execution (terrain + city + interiors + scatter + Tripo + visual verification)
**Confidence:** HIGH (cross-referenced against codebase, V9_MASTER_FINDINGS, 22 research docs, existing pipeline code)

## Summary

Phase 48 is the FINAL PHASE of v10.0. Unlike all previous phases that fixed bugs, wired dead code, and improved geometry, Phase 48 is an **execution phase** -- it runs the full compose_map pipeline to generate a complete Hearthvale starter city in Blender, then visually verifies every area meets AAA quality.

This phase depends on ALL prior phases (39-47) being complete. The terrain system, material system, vegetation scatter, settlement generator, interior binding, modular building kit, road network, export pipeline, and Unity bridge must all be working. Phase 48 does not write new generator code -- it CALLS the generators that previous phases fixed and wired, constructs the correct `map_spec` and `interior_spec` payloads, and iterates on visual quality until AAA.

**Primary recommendation:** Build the Hearthvale map_spec as a large multi-step orchestration using `asset_pipeline action=compose_map`, then `asset_pipeline action=compose_interior` for each key building, then `asset_pipeline action=generate_3d` (Tripo) for hero props. Use `asset_pipeline action=aaa_verify` and zai tools (`analyze_image`) at every stage. The plan must be structured as a visual-feedback-loop: generate, screenshot, analyze, fix, regenerate until AAA.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CITY-01 | Generate full terrain with cliffs, waterfalls, rivers, multi-biome landscape | compose_map Step 2 (terrain) + Step 3 (water). Terrain preset "hills" or "mountains", erosion enabled, height_scale 20-30m, resolution 256+. River carving via env_carve_river. Cliff/waterfall terrain features now wired (Phases 39-42). |
| CITY-02 | Generate starter city (Hearthvale) with castle, walls, buildings, roads integrated into terrain | compose_map Step 5 (locations) using settlement_generator routed through _LOC_HANDLERS["settlement"] (fixed in Phase 39). Castle uses modular building kit (wired Phase 42). Roads via MST road network (wired Phase 42). |
| CITY-03 | Generate walkable interiors for key buildings (tavern, blacksmith, chapel, keep) | compose_interior pipeline (Step 9 of compose_map or standalone calls). 14 room types available. building_interior_binding.py now imported (fixed Phase 42). |
| CITY-04 | Populate with environmental assets (vegetation, rocks, props, scatter) | compose_map Step 7 (vegetation) + Step 8 (props). VEGETATION_GENERATOR_MAP now wired (Phase 42). L-system trees replacing lollipops. Biome-aware scatter with exclusion zones. |
| CITY-05 | Use Tripo for city props, interior furnishing, and environmental assets | asset_pipeline action=generate_3d with Tripo API/Studio. Hero props: market stall details, tavern sign, castle banner, well mechanism. Interior furnishing: tables, chairs, kegs, anvil, altar. |
| CITY-06 | zai visual verification -- every area must score AAA or fix+regenerate | asset_pipeline action=aaa_verify (10-angle automated scoring) + zai analyze_image for human-judgment quality. Fix-regenerate loop until all angles pass min_score=60. |
| CITY-07 | Full compose_map pipeline execution with all systems wired | Complete 10-step pipeline: clear scene, terrain, water, roads, locations, biome paint, vegetation, props, interiors, heightmap export. All systems from Phases 39-47 exercised. |
| TEST-01 | All existing tests pass (19,920+ baseline) | pytest suite in Tools/mcp-toolkit/tests/. Run full suite before and after. |
| TEST-02 | New tests for all fixed generators and wired systems | Tests for compose_map integration, settlement routing, interior binding, vegetation scatter. |
| TEST-03 | Visual regression -- zai before/after for each generator category | aaa_verify with capture_baseline=True, then screenshot_regression comparison. |
| TEST-04 | Opus verification scan after every phase -- follow-up rounds until CLEAN | Multi-round scan: generate, scan, fix, re-scan until zero issues. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Always verify visually** after Blender mutations. Use `blender_viewport action=contact_sheet` for thorough review.
- **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
- **Game readiness**: Run `blender_mesh action=game_check` before export.
- **Use seeds** for reproducible environment/worldbuilding generation.
- **Batch when possible**: `asset_pipeline action=batch_process`, `blender_animation action=batch_export`.
- **Blender is Z-up** -- code must use Z for vertical axis, not Y.
- **Dark fantasy palette**: Saturation <40%, Value 10-50%.
- **AAA visual quality demanded** -- user will cancel subscription if quality is not met. Verify ALL generation visually in Blender.
- **NEVER score quality from code review** -- must generate and visually verify in Blender.
- **Run follow-up bug scan rounds until CLEAN** -- never stop after one round if bugs were found.

## Standard Stack

### Core Tools (MCP)

| Tool | Action | Purpose | When to Use |
|------|--------|---------|-------------|
| `asset_pipeline` | `compose_map` | Full 10-step world generation | Main terrain+city pipeline |
| `asset_pipeline` | `compose_interior` | Room shells + furniture + props | Tavern, blacksmith, chapel, keep interiors |
| `asset_pipeline` | `generate_3d` | Tripo AI 3D generation | Hero props, unique furnishings |
| `asset_pipeline` | `generate_building` | Tripo architecture presets | Unique landmark buildings |
| `asset_pipeline` | `aaa_verify` | 10-angle automated quality scoring | After every generation step |
| `blender_viewport` | `contact_sheet` | Multi-angle visual review | Visual QA after mutations |
| `blender_mesh` | `game_check` | Geometry validation | Before any export |
| `blender_worldbuilding` | `generate_hearthvale` | Standalone Hearthvale generation | Alternative to compose_map if needed |
| `blender_worldbuilding` | `generate_castle` | Castle structure generation | If compose_map castle needs regen |
| `blender_environment` | Various | Terrain/scatter/water individual ops | Targeted fixes |

### Visual Analysis (zai)

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `analyze_image` | General quality assessment | Score every screenshot against AAA bar |
| `ui_diff_check` | Compare expected vs actual | Before/after regeneration comparison |
| `extract_text_from_screenshot` | Read error messages from Blender | Debug generation failures |

### Supporting Infrastructure

| Library/Tool | Version | Purpose |
|-------------|---------|---------|
| Python | 3.13.12 | Test runner, MCP server |
| pytest | >=8.0 | Test suite (19,920 tests) |
| Blender | 4.4 or 5.0 | 3D generation target (localhost:9876) |
| Tripo API/Studio | Current | AI 3D model generation for hero props |

## Architecture Patterns

### Map Spec Structure (compose_map Input)

The compose_map action requires a detailed `map_spec` JSON. This is the CENTRAL artifact that drives the entire generation.

```json
{
  "name": "Hearthvale_Region",
  "seed": 42,
  "terrain": {
    "preset": "hills",
    "size": 300,
    "resolution": 256,
    "height_scale": 25.0,
    "erosion": true,
    "erosion_iterations": 8000
  },
  "water": {
    "rivers": [
      {"source": [20, 20], "destination": [280, 280], "width": 6, "depth": 3.0},
      {"source": [150, 10], "destination": [200, 280], "width": 4, "depth": 2.0}
    ],
    "water_level": 2.5
  },
  "roads": [
    {"waypoints": [[50, 150], [100, 150], [150, 150], [200, 150]], "width": 5},
    {"waypoints": [[150, 50], [150, 100], [150, 200], [150, 250]], "width": 4}
  ],
  "locations": [
    {
      "type": "settlement",
      "name": "Hearthvale",
      "districts": 5,
      "interiors": [
        {
          "rooms": [
            {"name": "tavern_hall", "type": "tavern_hall", "width": 12, "depth": 14, "height": 4.5},
            {"name": "tavern_kitchen", "type": "kitchen", "width": 6, "depth": 7, "height": 3.5}
          ],
          "doors": [{"from": "tavern_hall", "to": "tavern_kitchen", "style": "wooden"}]
        }
      ]
    },
    {"type": "castle", "name": "Hearthvale_Castle"},
    {"type": "ruins", "name": "Ancient_Watchtower"}
  ],
  "biome": "thornwood_forest",
  "vegetation": {"density": 0.6, "max_instances": 5000},
  "atmosphere": "foggy",
  "props": true,
  "prop_density": 0.4
}
```

### Interior Spec Structure (compose_interior Input)

Each key building needs a separate compose_interior call:

```json
{
  "name": "Hearthvale_Tavern",
  "seed": 42,
  "rooms": [
    {"name": "main_hall", "type": "tavern_hall", "width": 12, "depth": 14, "height": 4.5},
    {"name": "kitchen", "type": "kitchen", "width": 6, "depth": 7, "height": 3.5},
    {"name": "cellar", "type": "storage", "width": 10, "depth": 10, "height": 3, "below_ground": true},
    {"name": "upstairs_rooms", "type": "bedroom", "width": 12, "depth": 14, "height": 3}
  ],
  "doors": [
    {"from": "main_hall", "to": "kitchen", "style": "wooden"},
    {"from": "main_hall", "to": "cellar", "style": "trapdoor"},
    {"from": "main_hall", "to": "upstairs_rooms", "style": "staircase"}
  ],
  "style": "medieval",
  "storytelling_density": 0.7,
  "generate_props_with_tripo": false
}
```

### Generation Pipeline (10 Steps in compose_map)

```
Step 1:  Clear scene
Step 2:  Generate terrain (heightmap + erosion)
Step 3:  Water bodies (river carving + water plane)
Step 4:  Roads (MST network, terrain-following)
Step 5:  Place locations (settlement + castle + ruins)
         -> terrain flatten zone at each anchor
         -> foundation profile computation
         -> settlement_generator for Hearthvale
Step 6:  Biome paint (terrain materials + lighting)
Step 7:  Vegetation scatter (L-system trees, bushes, grass)
Step 8:  Prop scatter (contextual: near buildings)
Step 9:  Generate interiors (linked interior per key building)
Step 10: Export heightmap (.raw for Unity)
```

### Visual Verification Loop Pattern

Every major generation step follows this pattern:

```
1. Generate content (compose_map step or standalone tool)
2. Capture screenshots (contact_sheet for multi-angle)
3. Run aaa_verify (automated 10-angle scoring, min_score=60)
4. Analyze with zai (analyze_image for subjective quality)
5. IF score < threshold OR zai identifies issues:
   a. Identify specific problem (material, geometry, placement)
   b. Fix (adjust params, regenerate specific element)
   c. Return to step 2
6. ELSE: proceed to next step
```

### Recommended Project Structure for Generated Content

```
Blender Scene:
  Collection: Hearthvale_Region
    Collection: Terrain
      Hearthvale_Region_Terrain  (heightmap mesh)
      Hearthvale_Region_Water    (river + water plane)
    Collection: Roads
      Road_0, Road_1, ...        (road meshes)
    Collection: Locations
      Hearthvale                 (settlement: buildings, walls, roads)
      Hearthvale_Castle          (castle: keep, walls, towers, gate)
      Ancient_Watchtower         (ruins)
    Collection: Vegetation
      Trees, Bushes, Grass       (scattered vegetation)
    Collection: Props
      Contextual props           (near buildings)
    Collection: Interiors
      Hearthvale_Tavern_Interior
      Hearthvale_Blacksmith_Interior
      Hearthvale_Chapel_Interior
      Hearthvale_Castle_Keep_Interior
    Collection: Tripo_Props
      Hero props from Tripo AI
```

### Anti-Patterns to Avoid

- **Running compose_map once and accepting the result.** The output WILL have issues on the first run. Plan for 2-3 iterations minimum.
- **Skipping visual verification between steps.** Each step can introduce issues that compound. Catch early.
- **Using generate_hearthvale standalone instead of compose_map.** The standalone handler is simplified and bypasses terrain integration, material wiring, and vegetation scatter.
- **Generating all Tripo props at once.** Tripo has API rate limits. Queue props in batches of 3-5 with verification between batches.
- **Trusting automated aaa_verify scores alone.** The automated scorer checks brightness/contrast/edge/entropy/color but CANNOT judge aesthetic quality. zai analyze_image provides the subjective judgment.
- **Not using seeds.** Every generation call must include a seed for reproducibility. When regenerating, change the seed by +1 to get variation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Terrain generation | Custom heightmap code | `compose_map` Step 2 (env_generate_terrain) | Erosion, biome painting, material assignment all built in |
| City layout | Manual building placement | settlement_generator.py (15 types, layout patterns) | Organic growth model, road network, zone system |
| Interior rooms | Manual room geometry | compose_interior pipeline (14 room types) | Room shells, doors, furniture, storytelling props |
| Vegetation | Individual tree placement | VEGETATION_GENERATOR_MAP + env_scatter_vegetation | L-system trees, biome-aware density, exclusion zones |
| Hero 3D props | Procedural mesh for unique items | Tripo AI (asset_pipeline action=generate_3d) | Much higher visual quality for unique props |
| Quality scoring | Manual screenshot review only | aaa_verify (automated) + zai analyze_image (subjective) | Consistent, repeatable, catches issues humans miss |
| Foundation profiles | Manual terrain flattening | compose_map auto-computes foundation_profile per location | Height sampling, retaining walls, stair generation |

**Key insight:** Phase 48 is an INTEGRATION TEST of all prior phases. If something fails, the fix belongs in the prior phase's system, not in new code. Phase 48 should write ZERO new generator code -- only map_spec configuration and visual iteration.

## Common Pitfalls

### Pitfall 1: Settlement Handler Routing Still Broken
**What goes wrong:** compose_map routes "castle" to `world_generate_castle` (box generator) instead of `world_generate_settlement` with castle type.
**Why it happens:** Phase 39 was supposed to fix `_LOC_HANDLERS` dispatch but the fix may not have been applied to all entries.
**How to avoid:** Before running compose_map, verify `_LOC_HANDLERS["castle"]` routes to `world_generate_settlement` (not `world_generate_castle`). If still broken, this is a blocker -- must fix in Phase 39's territory.
**Warning signs:** Castle output is boxes instead of modular kit pieces.

### Pitfall 2: Z=0 Objects After Generation
**What goes wrong:** Buildings, vegetation, props placed at Z=0 instead of terrain height.
**Why it happens:** 42 instances of Z=0 hardcoding were documented in V9_MASTER_FINDINGS. Phase 39 should have replaced them with `_sample_scene_height()`.
**How to avoid:** After generation, run a scene audit checking all object Z positions against terrain height at (X, Y). Any object more than 0.5m below terrain or more than 2m above is suspect.
**Warning signs:** Objects underground, floating above terrain, or clustered at Z=0.

### Pitfall 3: Default Grey Materials
**What goes wrong:** Generated objects have no materials -- render as default grey/white.
**Why it happens:** Generators create geometry but the material wiring (Phase 40) may not be applied to all objects.
**How to avoid:** After generation, check aaa_verify for "default_material_detected" flag (color std_dev < 8). If flagged, run material assignment passes.
**Warning signs:** aaa_verify fails with "default_material_detected". Screenshots look uniformly grey.

### Pitfall 4: Vegetation on Water/Cliffs
**What goes wrong:** Trees growing in rivers, grass on cliff faces, bushes outside terrain bounds.
**Why it happens:** Vegetation scatter exclusion zones may not be properly configured for water bodies and steep slopes.
**How to avoid:** Verify vegetation scatter uses slope enforcement (no trees > 35 degrees) and water body exclusion. Check scene for objects inside water mesh bounds.
**Warning signs:** Trees visible in river, grass on vertical cliff faces.

### Pitfall 5: Blender Memory/Crash on Large Scenes
**What goes wrong:** Blender crashes or becomes unresponsive generating a full 300x300m world with thousands of objects.
**Why it happens:** Large vertex counts, many materials, high vegetation density exceed Blender memory.
**How to avoid:** Use budget parameters. Start with smaller terrain (200m) and lower density. Use checkpoint_dir for resume capability. Monitor Blender responsiveness.
**Warning signs:** Blender stops responding to TCP commands, timeout errors.

### Pitfall 6: Tripo API Rate Limits / Key Missing
**What goes wrong:** Tripo generation fails with auth errors or rate limiting.
**Why it happens:** TRIPO_API_KEY not set, or session cookie expired, or too many concurrent requests.
**How to avoid:** Verify TRIPO_API_KEY is set in environment before starting Tripo generation. Generate props in batches of 3-5. Use Tripo Studio (session cookie) for subscription credits.
**Warning signs:** "Error: authentication failed" or 429 responses.

### Pitfall 7: aaa_verify Screenshot Bug (EXPORT-08)
**What goes wrong:** aaa_verify uses stale screenshots -- old PNGs from previous runs are scored instead of current state.
**Why it happens:** Screenshots go to a fixed directory (`vb_aaa_verify` in temp) and may not be overwritten if the render_angle command fails silently.
**How to avoid:** Clear the aaa_verify temp directory before each verification pass. Verify screenshot timestamps match current time.
**Warning signs:** Quality scores don't change after regeneration. Screenshot paths exist but content is outdated.

### Pitfall 8: Checkpoint Resume Resets Interior Results
**What goes wrong:** On resume, interior_results list is cleared.
**Why it happens:** BUG-CHKPT-01 in compose_map -- `interior_results = []` is inside the "interiors_generated" guard, which means on resume from a crash AFTER some interiors were generated, those results are lost.
**How to avoid:** If using checkpoint resume and interiors were partially generated, set force_restart=True and regenerate from scratch rather than resuming.
**Warning signs:** Location results present but interior_results empty after resume.

## Code Examples

### Example 1: Full Hearthvale compose_map Call

```python
# Via MCP tool call:
asset_pipeline(
    action="compose_map",
    map_spec={
        "name": "Hearthvale_Region",
        "seed": 42,
        "terrain": {
            "preset": "hills",
            "size": 250,
            "resolution": 256,
            "height_scale": 25.0,
            "erosion": True,
            "erosion_iterations": 8000
        },
        "water": {
            "rivers": [
                {"source": [30, 30], "destination": [220, 220], "width": 6, "depth": 3.0}
            ],
            "water_level": 2.5
        },
        "roads": [
            {"waypoints": [[50, 125], [125, 125], [200, 125]], "width": 5},
            {"waypoints": [[125, 50], [125, 200]], "width": 4}
        ],
        "locations": [
            {
                "type": "settlement",
                "name": "Hearthvale",
                "districts": 5,
                "interiors": [
                    {
                        "rooms": [
                            {"name": "tavern_main", "type": "tavern_hall", "width": 12, "depth": 14, "height": 4.5},
                            {"name": "tavern_kitchen", "type": "kitchen", "width": 6, "depth": 7, "height": 3.5}
                        ],
                        "doors": [{"from": "tavern_main", "to": "tavern_kitchen", "style": "wooden"}]
                    }
                ]
            },
            {"type": "castle", "name": "Hearthvale_Castle"},
            {"type": "ruins", "name": "Ancient_Watchtower"}
        ],
        "biome": "thornwood_forest",
        "vegetation": {"density": 0.5, "max_instances": 4000},
        "atmosphere": "foggy",
        "props": True,
        "prop_density": 0.35
    },
    checkpoint_dir="C:/Users/Conner/AppData/Local/Temp/veilbreakers_hearthvale"
)
```

### Example 2: Standalone Interior Generation (Blacksmith)

```python
asset_pipeline(
    action="compose_interior",
    interior_spec={
        "name": "Hearthvale_Blacksmith",
        "seed": 43,
        "rooms": [
            {"name": "forge_room", "type": "forge", "width": 8, "depth": 10, "height": 4},
            {"name": "shop_front", "type": "shop", "width": 6, "depth": 8, "height": 3.5},
            {"name": "storage", "type": "storage", "width": 5, "depth": 5, "height": 3}
        ],
        "doors": [
            {"from": "forge_room", "to": "shop_front", "style": "wooden"},
            {"from": "shop_front", "to": "storage", "style": "wooden"}
        ],
        "style": "medieval",
        "storytelling_density": 0.8,
        "generate_props_with_tripo": False
    }
)
```

### Example 3: Tripo Hero Prop Generation

```python
# Generate a unique tavern sign
asset_pipeline(
    action="generate_3d",
    prompt="dark fantasy medieval tavern hanging sign, wrought iron bracket, painted wooden board, weathered text, game-ready 3D model, PBR textures",
    name="Tavern_Sign",
    seed=42
)

# Generate a market well
asset_pipeline(
    action="generate_3d",
    prompt="dark fantasy medieval stone well, iron chain mechanism, moss-covered stone, bucket, wooden roof cover, game-ready 3D model, PBR textures",
    name="Market_Well",
    seed=43
)
```

### Example 4: Visual Verification Loop

```python
# Step 1: Run aaa_verify on the generated scene
result = asset_pipeline(action="aaa_verify", angles=10, min_score=60)

# Step 2: Check which angles failed
if not result["verification"]["passed"]:
    for angle in result["verification"]["per_angle"]:
        if not angle["passed"]:
            # Use zai to analyze the specific failing screenshot
            # analyze_image on the screenshot path
            # Identify the issue and fix
            pass

# Step 3: After fixes, re-verify
result2 = asset_pipeline(action="aaa_verify", angles=10, min_score=60)
```

## State of the Art

| Old Approach (v8.0) | Current Approach (v10.0 Phase 48) | When Changed | Impact |
|---------------------|-----------------------------------|--------------|--------|
| Castle = box generator | Castle routed through settlement_generator + modular building kit | Phase 39/42 | Castles use 260-piece kit with 5 styles |
| Vegetation = 6 template meshes | VEGETATION_GENERATOR_MAP with L-system trees | Phase 42 | Oak/birch/twisted/dead trees, real shrubs |
| Water = flat quad | Spline-following water mesh + flow vertex colors | Phase 42 | Shaped river meshes following terrain |
| Roads = simple paths | MST road network with curb geometry | Phase 42 | Organic road layout, proper intersections |
| Material = default grey | 52 materials + 6 procedural generators + 14 biome palettes | Phase 40 | Full PBR with height-blended terrain |
| Interiors = not imported | building_interior_binding.py wired into settlement gen | Phase 42 | 14 room types with furniture + props |
| Z=0 placement | _sample_scene_height() for terrain-aware placement | Phase 39 | Objects at correct terrain elevation |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio |
| Config file | `Tools/mcp-toolkit/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q --timeout=30` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CITY-01 | Terrain with cliffs, rivers, multi-biome | integration | Visual verification in Blender (manual with aaa_verify) | N/A -- runtime test |
| CITY-02 | Settlement with castle, walls, buildings | integration | Visual verification in Blender | N/A -- runtime test |
| CITY-03 | Walkable interiors (tavern, blacksmith, chapel, keep) | integration | `python -m pytest tests/test_mesh_enhance.py -k compose_interior -x` | Exists (partial) |
| CITY-04 | Environmental assets (vegetation, rocks, props) | integration | Visual verification in Blender | N/A -- runtime test |
| CITY-05 | Tripo for city props | integration | Requires TRIPO_API_KEY + live Tripo API | N/A -- runtime test |
| CITY-06 | zai visual verification AAA | integration | `asset_pipeline action=aaa_verify` | N/A -- runtime test |
| CITY-07 | Full compose_map pipeline | integration | `python -m pytest tests/test_compose_map_integration.py -x` | Exists |
| TEST-01 | All existing tests pass | unit/integration | `cd Tools/mcp-toolkit && python -m pytest tests/ -q` | Exists (19,920) |
| TEST-02 | New tests for fixed generators | unit | Wave 0 gap -- need new test files | Wave 0 |
| TEST-03 | Visual regression | integration | `asset_pipeline action=screenshot_regression` | N/A -- runtime |
| TEST-04 | Opus verification scan | manual | Multi-round scan with fix iterations | N/A -- manual |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q --timeout=30`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -q`
- **Phase gate:** Full suite green + aaa_verify passed + zai analyzed before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_city_generation_integration.py` -- covers CITY-01 through CITY-07 (map_spec construction, pipeline step sequence, output validation)
- [ ] `tests/test_tripo_prop_generation.py` -- covers CITY-05 (Tripo prompt construction, post-processing)
- [ ] `tests/test_visual_verification_loop.py` -- covers CITY-06 (aaa_verify score thresholds, regression baseline)

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Blender | All CITY-* reqs | Yes | 4.4 and 5.0 installed | Use Blender 5.0 (target) |
| Python | Test suite, MCP server | Yes | 3.13.12 | -- |
| pytest | TEST-01 | Yes | >=8.0 (pyproject.toml) | -- |
| Blender addon (TCP :9876) | All generation | Requires manual start | -- | Must start Blender with addon before execution |
| Tripo API | CITY-05 | Requires TRIPO_API_KEY env var | -- | Skip Tripo props, use procedural fallbacks |
| zai MCP tools | CITY-06 | Available via MCP | -- | Fall back to aaa_verify automated scoring only |

**Missing dependencies with no fallback:**
- Blender must be running with VeilBreakers addon connected on localhost:9876. This is a manual prerequisite.

**Missing dependencies with fallback:**
- TRIPO_API_KEY may not be set. Fallback: use procedural generators for all props instead of Tripo AI.

## Open Questions

1. **Blender 4.4 vs 5.0 compatibility**
   - What we know: Both are installed. Blender 5.0 has API changes (group.inputs.new removed, Musgrave replaced with Noise).
   - What's unclear: Whether Phase 39 (PIPE-03) fully fixed all Blender 5.0 API deprecations.
   - Recommendation: Test with Blender 5.0 first. If API errors occur, fall back to 4.4.

2. **Settlement scaling for Hearthvale**
   - What we know: settlement_generator has village=4-8 buildings, town=8-16 buildings. V9 findings noted city=20-40 (code) vs plan=100+ (design intent).
   - What's unclear: Whether Phase 45 (SAFE-05) adjusted settlement scaling or if Hearthvale will generate with only 8-16 buildings.
   - Recommendation: Override building_count in map_spec to 25-40 for Hearthvale. Use districts=5 to force zone diversity.

3. **Terrain size for playable city**
   - What we know: Current test scenes use 200x200m terrain.
   - What's unclear: Whether 200m is large enough for a full city + surrounding landscape + terrain features.
   - Recommendation: Use 250-300m terrain. Larger terrain needs higher resolution (256+) to maintain vertex density.

4. **Tripo credit budget**
   - What we know: Tripo Studio uses subscription credits, Tripo API uses API credits.
   - What's unclear: How many credits are available, how many props can be generated.
   - Recommendation: Budget 15-20 Tripo generations for hero props. Prioritize unique items (tavern sign, market well, castle banner, altar) over generic furniture.

5. **Interior streaming integration**
   - What we know: Interiors are generated as separate geometry. building_interior_binding produces interior_scene_name.
   - What's unclear: Whether the generated interiors are positioned correctly relative to building exteriors.
   - Recommendation: After interior generation, verify position alignment by comparing interior bounds with building exterior bounds.

## Hearthvale City Design Specification

Based on castle_terrain_medieval_landscape_research.md and AAA_ARCHITECTURE_VISUAL_STANDARDS.md:

### Terrain Layout
- **Size:** 250x250m (larger if memory allows, 300x300m preferred)
- **Height range:** 0-25m (terrain height_scale=25.0)
- **Elevation zones:**
  - Valley floor (0-5m): River, farms, approach roads
  - Hillside (5-15m): Town with walls, winding streets
  - Hilltop (15-25m): Castle with keep, towers, gatehouse
  - Cliff face: On one or two sides for natural defense

### Castle (Hilltop)
- Modular kit pieces: keep, curtain walls (2-3m thick), corner towers, gatehouse with arch
- Wall height: 8-12m, tower height: 15-20m (1.3-1.5x wall height)
- Merlons: 1.0-1.5m high, 0.6-0.8m wide (one-third rule)
- Castle courtyard with chapel interior access
- Materials: 3-5 stone types (base plinth, main wall, parapet)

### Town (Hillside)
- Settlement type: "town" or "settlement" with 5 districts
- Ward system: market square at center, artisan quarter, residential, military, religious
- Roads: cobblestone main streets (4-6m), packed earth secondary (2-4m)
- Building density decreases from center outward
- Town walls following contour of buildable land

### Key Buildings (with interiors)
1. **Tavern** -- main hall (12x14m), kitchen (6x7m), cellar, upstairs rooms
2. **Blacksmith** -- forge room (8x10m), shop front (6x8m), storage
3. **Chapel** -- nave (10x15m), vestry (5x5m)
4. **Castle Keep** -- great hall (15x20m), armory (8x8m), throne room (10x12m)

### Environmental Assets
- L-system trees: oak and twisted near town, dead near corruption zone
- Undergrowth: bushes, grass clumps, ferns, mushrooms
- Rocks: 2-6 types, partially embedded (10-30% sunk into terrain)
- Road props: milestones, wayside shrines, signposts
- Town props: market stalls, well, carts, barrels, crates

### River
- Source in hills (NW), flows through valley floor (SE)
- Width: 5-8m, carved into terrain with smooth banks (5-15 degrees, not staircases)
- Ford crossing point near town (shallow gravel bed)
- Waterfall where river meets cliff edge

### Biome
- Primary: thornwood_forest or temperate woodland
- Dark fantasy palette: desaturated greens, earth tones, weathered greys
- Corruption gradient from one edge (hints of purple/sickly green)

## Sources

### Primary (HIGH confidence)
- V9_MASTER_FINDINGS.md -- 53-agent audit, 800+ lines, all system status documented
- blender_server.py compose_map implementation (lines 2737-3229) -- actual pipeline code
- blender_server.py compose_interior implementation (lines 3526-3720) -- actual interior code
- settlement_generator.py SETTLEMENT_TYPES (lines 39-120) -- actual settlement configs
- visual_validation.py aaa_verify_map (lines 136-200) -- actual verification logic

### Secondary (MEDIUM confidence)
- castle_terrain_medieval_landscape_research.md -- historical castle dimensions, terrain composition rules
- AAA_ARCHITECTURE_VISUAL_STANDARDS.md -- FromSoftware/Bethesda quality bar
- AAA_PROCEDURAL_CITY_TERRAIN_BEST_PRACTICES.md -- city generation patterns
- MEDIEVAL_BUILDING_INTERIORS_REFERENCE.md -- room types and furnishing

### Tertiary (LOW confidence)
- Settlement scaling may have changed in Phases 39-47 (not verified against current code)
- Tripo credit availability and rate limits (depends on user's subscription)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- tools are documented in codebase and MCP system-reminder
- Architecture: HIGH -- compose_map and compose_interior code examined directly
- Pitfalls: HIGH -- all documented in V9_MASTER_FINDINGS with line-level specificity
- City design spec: MEDIUM -- based on research docs, not yet validated by generation

**Research date:** 2026-04-04
**Valid until:** 2026-04-14 (10 days -- active development may change system state)
