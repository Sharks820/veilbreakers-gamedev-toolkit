# Procedural Terrain Best Practices — Synthesis

**Source video:** runevision, *"Fast & Gorgeous Erosion Filter Explained"* (blog.runevision.com, 2026-03).
**Context:** Applied to the VeilBreakers terrain audit (`FINDINGS.md`, ~630 findings, 5 divergent authoring paths, dead-delta epidemic).

---

## 1. The core insight from the video

runevision's filter is **analytical, not simulated**. Every point on the heightfield is evaluated in isolation from `(x, z)` plus the base height function's analytical gradient. No droplet loops, no grid iterations, no history — which means:

- **Chunk-parallel**: works for streamed / infinite worlds. Our current sim-based passes can never chunk.
- **GPU-friendly**: single pass per point.
- **Composable**: applies *on top of* any base height (Perlin, ridged, heightmap import).
- **Deterministic & reproducible**: no accumulation bugs, no droplet-count tuning.

Technique in one paragraph: divide space into Worley-like cells with random pivots; at each cell emit an anisotropic cosine/sine wave pair oriented along the **local gradient** (water-flow direction) — cosine becomes the gully depth offset, sine becomes the slope contribution. Blend neighbouring cells (two unaligned sines sum to a smaller-amplitude sine, so it's naturally smooth). Stack octaves with an **adaptive combi-mask** where each octave's contribution is gated by the previous octave's ridge/crease pattern. Use `sign(sine_derivative)` instead of `sine_derivative` to get triangle-wave straight-slope gullies that branch cleanly. Run a parallel pass without gully-weight/rounding to get a **ridge map** (black creases, white ridges) — that's your river-drainage network, free.

Outputs per point: `height_offset`, analytical `∂h/∂x, ∂h/∂z` (for normals/shading), `ridge_map` value (for rivers/flow).

## 2. Why this matters for our audit

The video maps onto our pain points 1:1:

| Audit finding | Video-technique answer |
|---|---|
| F277 broken droplet gravity sign (`speed_sq = speed² + Δh·g`) | Delete droplet sim entirely. Use analytical filter. Sign bug becomes impossible. |
| F003-family dead deltas (pass_caves, pass_waterfalls computing then discarding geometry) | One pass, one additive `height_offset`. No side channels. |
| 5 divergent authoring paths (pass DAG, compose_terrain_node, compose_map, internal cliff overlays, cowork_bridge scripts) | Single `erosion_filter(x, z, base_height_fn)` callable from all five paths. |
| F461 global MagicMock bpy in conftest (tests hid everything) | Analytical filter is pure numpy/math — unit-testable against known gradients without any Blender stub. |
| Missing pipe-flux / Strahler / drainage (F113-F129) | Ridge map *is* the drainage network. Strahler order fallout from ridge-map skeletonization. |
| No chunked/streamed terrain possible today | Per-point evaluation ⇒ trivially chunkable. |

## 3. AAA best-practices checklist (tie to findings)

Ordered by ROI for our codebase.

1. **Replace droplet hydraulic erosion with an analytical filter pass.**
   Kill `_terrain_noise.hydraulic_erosion` (F277) and every consumer. Add `terrain_erosion_filter.apply(stack, params)` modeled on the runevision algorithm. One pass, one height write, analytical gradient output reused for the Blender mesh normals.

2. **Single integrator stage, not 31 side-channel passes.**
   Pass DAG stays, but every pass writes to `stack.height` (or a dedicated `delta` the integrator composes). Forbid orphan channels via AST lint rule (add to `quality_lint.py`). Closes the entire dead-delta finding class (F003-family, F601, F604).

3. **Ridge-map drainage network as first-class output.**
   The filter produces a ridge map "for free." Feed it to river placement (F113-F117) — rivers trace the darkest ridge-map crests, meander via sine distortion in the gradient domain, Strahler order by skeleton-pixel-neighbour count. No more "rivers don't look like rivers."

4. **Triplanar material projection, not UV.**
   Current material stack assigns base color *before* splatmap attribute exists (F-material-2382). For AAA cliff/canyon faces, triplanar sampling on world-space position + slope mask is the industry baseline (Horizon, God of War, Valheim). UV only for hero assets.

5. **Macro + detail normal blending.**
   Analytical filter gives the macro normal for free. Detail normal comes from a second high-freq filter pass. Combine with Reoriented Normal Mapping. Matches the video's octave-stacking pattern.

6. **Chunked terrain = layered generation (LayerProcGen).**
   runevision's companion library `LayerProcGen` is the canonical answer to "how do I stream this at runtime without seams." If we ever want Unity runtime streaming (feedback_realtime_editing_scalability.md), this is the pattern.

7. **Height function as a pure callable, not a Blender object.**
   `environment_scatter:1690` does `_terrain_height_sampler(bpy.data.objects.get(area_name))` with silent Z=0 fallback. Height should be a `Callable[[float, float], float]` passed around, never a Blender object lookup. Makes tests possible, makes chunks possible, kills the silent-fallback family.

8. **Decouple pass DAG from render path — but via a *contract*, not by having both do their own thing.**
   Today `compose_terrain_node` hardcodes `erosion="none"` (F-environment-3382) because the pass DAG and render path don't trust each other. Fix: the DAG produces a `BakedTerrain` artifact (height grid + ridge map + material masks + metadata). Render path *only* consumes `BakedTerrain`. No direct calls to `env_generate_terrain` from compose_*.

9. **Delete bug-ratifying tests.**
   `tests/test_terrain_waterfalls.py:335` asserts `height == h_before` — that literally enforces the dead-delta bug. Per `feedback_no_bug_ratifying_tests.md`, delete and replace with a test that fails today and passes after the integrator fix.

10. **Kill the global MagicMock bpy stub.**
    `tests/conftest.py:11-98` is the meta-reason nothing gets caught. Replace with a real `fake_bpy` module that errors loudly on unimplemented attrs. `feedback_test_substance_bar.md` applies — every test should fail if the function body is `pass`.

## 4. Concrete fix sequence (atomic commits)

1. `fix: correct hydraulic erosion gravity sign` — one-line fix at `_terrain_noise.py:928`. Immediate smoke test. (Buys us a working baseline even before the rewrite.)
2. `feat: add terrain_erosion_filter analytical pass` — new module, pure numpy, unit tests against known gradients.
3. `refactor: route pass_caves/pass_waterfalls deltas through stack.height` — closes dead-delta class.
4. `feat: BakedTerrain artifact + single integrator stage` — the contract.
5. `refactor: compose_terrain_node consumes BakedTerrain` — unifies paths 1 & 2.
6. `refactor: compose_map consumes BakedTerrain` — unifies path 3.
7. `test: replace global MagicMock conftest with fake_bpy` — unblocks every future test.
8. `fix: delete bug-ratifying waterfall test` — per policy.
9. `feat: ridge-map-driven river network` — delivers on F113-F117.
10. `feat: triplanar + macro/detail normal material` — delivers AAA visual bar.

Each commit atomic, each commit the smallest thing that could possibly work, each commit independently revertable.

## 5. What the video does NOT solve for us

- **Hero terrain nodes** (Riftpass_01 hand-carved cliffs): analytical filter is global; hero geometry still needs the cliff-face-builder path. The filter just stops actively fighting it.
- **Cave volumes**: analytical erosion is surface-only. Caves need the volumetric builder path — but it should emit a mesh, not a discarded `_delta`.
- **Tripo environmentals**: orthogonal — still need to wire `asset_pipeline.compose_terrain_node` to actually call Tripo instead of the stub path.

## 6. Community best practices (Reddit thread on the video)

Raw community wisdom that's directly actionable for us:

### 6.1 Slope-threshold instancing (the simplest possible scatter rule)

```
slope = 1.0 - dot(surface_normal, world_up)   # 0 = flat, 1 = vertical

if   slope > HI:   spawn sheer_rock_cliff      # vertical faces
elif slope > MID:  spawn stair_stepped_rock    # walkable steep
elif slope > LOW:  spawn small_rock_scatter    # rolling
else:              spawn path_or_grass         # flat
```

Plus "post break-up to taste" — jitter spawn points, rotate randomly, vary scale, mask by curvature/noise to avoid grid artifacts.

**Maps to our audit:** `environment_scatter.py` today uses `_terrain_height_sampler(bpy.data.objects.get(area_name))` with a silent Z=0 fallback — it doesn't even know what the slope is. Fix: scatter reads `analytical_gradient` from the `BakedTerrain` artifact (section 3, item 1) and branches on `1 - n·ẑ`. Four prefab buckets, four thresholds, done. Replaces most of the current stub-filled scatter logic.

### 6.2 Slope angle is just a dot product (Far_Oven_3302)

`dot(normal, up)` gives `cos(angle)`. That's the whole "how steep is this point" calculation. No trig needed, one multiply-add per axis. Works per-vertex, per-pixel, or in the scatter pass. **We already have analytical gradients from the erosion filter (section 1)** — this is literally free once that lands.

### 6.3 Stairs = steep + path overlay (leorid9)

The insight is that **stairs are not a third surface class** — they're the *intersection* of "steep slope" and "path network." Base layer picks grass-or-rock by angle. Then a path mask does a compound swap:

```
if path_mask:
    if base == grass: → dirt_path
    if base == rock:  → stone_stairs
```

**Maps to our audit:** we currently have no path network at all, and the "stair" handling is hardcoded in hero builders. Better: generate a path graph (A\* between POIs on the heightfield, cost = slope²) → rasterize into a `path_mask` channel → material/scatter stages both consume it. Stairs emerge, they aren't authored.

### 6.4 Triplanar mapping + persistent cliff-detail noise (gHx4)

Two things:

1. **Triplanar sampling** solves UV stretching on cliff faces — sample the texture three times (XY, YZ, XZ planes), blend by `normal²`. Standard AAA technique; already in section 3 item 4.
2. **Pre-generated persistent "cliffs layer" noise** that the shader samples independently of the heightmap. When the heightmap is perturbed (brush, edit, streaming chunk), the cracks and bumps in the cliff *stay put in world space* because they come from a separate persistent noise field, not from deforming a baked texture.

**Maps to our audit:** today the material system re-bakes textures on every edit and re-assigns base color *before* the splatmap attribute exists (F-material-2382). The cliff detail should be a **shader-time triplanar sample of a world-space noise volume**, not a baked VertexColor. That means:
- Material is authored once with a `cliff_detail_noise` input (3D simplex or a tiled 2D triplanar).
- Heightmap edits don't touch the material at all.
- Streamed chunks pick up the same noise seed → cliffs are seamless across chunk borders.
- `feedback_realtime_editing_scalability.md` (real-time edit→view→refine) finally works — edits only rewrite height, not textures.

This also kills the whole "material re-bake on every brush stroke" class of bugs.

### 6.5 Synthesis → add two items to the fix sequence

Inserting between items 9 and 10 of §4:

> 9a. `feat: slope-threshold scatter rules on BakedTerrain.gradient` — replaces stub-scatter with four-bucket dot-product rule + path-mask override for stairs.
>
> 9b. `feat: triplanar cliff shader with persistent world-space detail noise` — material stops re-baking on edits; cliffs stay seamless across streamed chunks.

## 7. Reference implementation: lpmitchell/AdvancedTerrainErosion

**Repo:** `https://github.com/lpmitchell/AdvancedTerrainErosion`
**License:** MIT + MPL-2.0 (compatible with our project)
**What:** Burst-compatible C# port of runevision's analytical erosion filter for Unity. Single file, ~600 lines, zero allocations.

### 7.1 Architecture (from source code review)

```
Sample(vec2 p, config, seed)
  ├── FractalNoise(p)           → base height + analytical derivatives (Inigo Quilez gradient noise)
  ├── fadeTarget = clamp(h / amplitude)   → -1 at valleys, +1 at peaks
  └── ErosionFilter(p, heightAndSlope, fadeTarget, ...)
       ├── for each octave:
       │    ├── PhacelleNoise(p*freq, normalize(gullySlope), cellScale, ...)
       │    │    └── 4×4 cell grid, cosine/sine stripe pairs oriented along slope
       │    │        blended with bell-curve weights exp(-dist²·2)
       │    ├── gullySlope += sign(sine) * derivatives * strength * gullyWeight
       │    │    └── (triangle-wave trick: straight gullies that branch cleanly)
       │    ├── fadedGullies = lerp(fadeTarget, gullies*gullyWeight, combiMask)
       │    ├── heightAndSlope += fadedGullies * strength
       │    ├── combiMask = PowInv(combiMask, detail) * newMask
       │    └── ridgeMapFadeTarget = lerp(ridgeMapFadeTarget, gullies.x, ridgeMapCombiMask)
       └── return (heightDelta, slopeDelta, magnitude), ridgeMap
```

**Output:** `ErosionSample { Height, RidgeWeight }` per point. RidgeWeight is -1 on creases (rivers), +1 on ridges.

### 7.2 Key design decisions we should adopt

1. **Config as a plain struct** — `ErosionConfig` has 12 fields, all `real` or `vecN`. No frozen-dataclass-with-mutable-list footguns. Maps cleanly to our terrain YAML contract.
2. **Per-pixel overrides** — `Sample()` accepts both a config *and* per-pixel overrides for strength/gullyWeight/detail/rounding/onset/assumedSlope. This means biome-blending is trivial: lerp configs at biome boundaries.
3. **Analytical derivatives throughout** — `FractalNoise` returns `vec3(height, dh/dx, dh/dz)`. Erosion filter preserves and updates derivatives. No finite-difference normal estimation needed.
4. **Cubemap projection for spherical** — 3D `Sample(direction)` projects to 6 faces with smooth blending. Future-proof for planetary terrain.
5. **Seed-based determinism** — `Hash2(x, seed)` uses irrational-number hash with seed offset. Reproducible, no global state.

### 7.3 Integration plan

**Blender side (Python/numpy port):**
- Port `ErosionFilter` + `PhacelleNoise` + `FractalNoise` to numpy (~100 lines of vectorized math).
- Replace `_terrain_noise.hydraulic_erosion` (F277) entirely.
- New module: `terrain_erosion_filter.py` with `apply(stack, config) → (height_delta, ridge_map)`.
- Unit-testable against known gradients — no Blender stub needed.

**Unity side (direct UPM dependency):**
- Add to VeilBreakers3DCurrent: `"com.lpmgames.terrain.erosion": "https://github.com/lpmitchell/AdvancedTerrainErosion.git?path=package"`
- Use `AdvancedTerrainErosion.Sample()` for runtime terrain eval in Unity terrain system.
- `RidgeWeight` feeds slope-threshold scatter (§6.1) and river placement.
- Burst + Jobs for terrain streaming chunks.

**Config mapping:**
| Our YAML field | → ErosionConfig field |
|---|---|
| `erosion_strength` | `Strength` |
| `erosion_scale` | `Scale` |
| `gully_weight` | `GullyWeight` |
| `detail` | `Detail` |
| `rounding` | `Rounding` (vec4) |
| `onset` | `Onset` (vec4) |
| `assumed_slope` | `AssumedSlope` (vec2) |
| `octaves` | `Octaves` |
| `lacunarity` | `Lacunarity` |
| `gain` | `Gain` |

## 8. Additional reference implementations (user-sourced)

### 8.1 Mei/Decaudin/Hu — Pipe-model GPU hydraulic erosion (INRIA 2007)

**Paper:** [Fast Hydraulic Erosion Simulation and Visualization on GPU](https://inria.hal.science/inria-00402079/document)

The canonical GPU erosion paper. Uses a **pipe model** (not droplets) for shallow-water simulation — water flows between grid cells through virtual "pipes" driven by hydrostatic pressure difference. This is the algorithm our `_terrain_erosion.py` *should* have implemented but didn't.

**Five-step simulation loop (per timestep):**
1. **Water increment**: `d₁ = d + Δt·rain`
2. **Flux update**: `f_new = max(0, f_old + Δt·A·g·Δh/L)` — flow through each pipe proportional to height difference
3. **Erosion/deposition**: Sediment capacity `C = Kc·sin(α)·|v|` — if capacity > suspended sediment → erode terrain; if less → deposit
4. **Sediment transport**: advect suspended sediment along velocity field (bilinear backtracking)
5. **Evaporation**: `d = d·(1 - Kₑ·Δt)`

**Why this matters for us:**
- Our droplet sim (F277, broken gravity sign) is the *wrong algorithm class*. Pipe-model is grid-parallel (GPU-friendly), physically motivated, and produces drainage networks naturally.
- However, it's still a **simulation** (needs history, can't chunk independently). For our tiled pipeline, the analytical filter (runevision) is better for the base layer. The pipe model is useful for **hero-node refinement** — after the analytical base, run a few pipe-model iterations on overlapping regions to add local detail (pooling, undercut banks, alluvial fans).
- The `C = Kc·sin(α)·|v|` capacity formula is what our `terrain_materials_v2.py` should use for splatmap weight computation: high capacity = exposed rock, low capacity = sediment/grass.

### 8.2 erosiv/soillib — GPU geomorphology library (C++23/CUDA)

**Repo:** [erosiv/soillib](https://github.com/erosiv/soillib)

Production CUDA library by Nick McDonald (author of Procedural Hydrology). Two erosion kernels:

**Hydraulic (`erosion.cu`):**
- Particle-based but GPU-parallelized with atomic operations
- Physics: suspension `= dt·ks·vol·slope·α·discharge^0.4`, deposition `= dt·kd·sed`
- Mass-clamped: `maxtransfer = 0.1·slope·|cl|/scale.z·Z·Q` for stability
- Velocity: implicit Euler with bed shear + viscosity + bulk momentum averaging
- Key insight: **discharge-dependent erosion** (discharge^0.4 exponent) — larger streams erode more than isolated droplets. Our code treats all droplets identically.

**Thermal (`erosion_thermal.cu`):**
- Debris flow particle simulation
- `stable_height = neighbor_h + critSlope·distance` — material above this threshold is suspended
- **Multi-material layering**: sediment buffer depletes before bedrock erodes (stratum separation)
- Our `apply_thermal_erosion_masks` has no material layering — it erodes a single-channel heightmap uniformly.

**Flow accumulation (`flow.hpp`):**
- Stochastic Monte Carlo flow routing + exhaustive deterministic variant
- 8-connected neighborhood with diagonal distance weighting (√2)
- `upstream()` for catchment masks, `distance()` for upstream distance
- This is the missing piece between our analytical ridge map and actual river geometry: ridge_map → flow accumulation → stream order → river width/depth.

**Integration path:** soillib is CUDA-only (Linux). We can't use it directly, but the algorithms port to numpy/cupy. The discharge-dependent erosion and multi-material layering are the two techniques to adopt.

### 8.3 otto-link/Hesiod + HighMap — Node-based terrain generation (C++)

**Repos:** [Hesiod](https://github.com/otto-link/Hesiod) (GUI) / [HighMap](https://github.com/otto-link/HighMap) (library)

Open-source World Machine alternative. **289 terrain operation nodes** including:
- Erosion: hydraulic, thermal, stratification
- Noise: fbm, ridged, swiss, Perlin, Worley
- Generators: caldera, basalt_field, badlands, bump, bump_lorentzian
- Filters: blur, clamp, clamp_oblique, closing, morphological ops
- Cloud/path/vector operations for scatter and roads

**Why this matters:**
- Hesiod's node graph is exactly what our pass DAG *should* be — each node is a pure function of inputs, composable, and the graph handles dependency ordering.
- The **289 node types** are a checklist of what AAA terrain tools need. We have ~31 passes; Hesiod has 289. The gap is the gap.
- `accumulation_curvature` node — computes curvature from flow accumulation, not just from the heightmap. Our curvature is heightmap-only (finite differences), missing flow-weighted curvature which is what makes valleys look concave and ridges convex.
- `badlands` and `caldera` generators — specialized geological feature generators. We have terrain_type presets ("volcanic", "canyon") but they're just noise parameter tweaks, not geological models.

**Integration path:** HighMap is C++ with no Python bindings. Too heavy to port directly. But the *node list* is a reference architecture — it tells us which operations to implement in our numpy pipeline. Priority nodes we're missing: `accumulation_curvature`, `stratify`, `badlands`, `caldera`, `sediment_deposition`.

### 8.4 Coastline Paradox approach (Reddit r/proceduralgeneration)

**Post:** [The Coastline Paradox Part Two](https://www.reddit.com/r/proceduralgeneration/comments/1r0zfva/the_coastline_paradox_part_two_how_to_generate/) (couldn't fetch full content — Reddit blocked)

From web search context: the approach uses fractal subdivision to generate coastlines — start with a simple polygon, recursively bisect edges and displace midpoints. Each iteration doubles point count. The "coastline paradox" (fractal dimension between 1 and 2) means more detail = longer perceived coastline.

**Why this matters for us:**
- Our `pass_coastline` (one of the 31 DAG passes) currently exists but was flagged as a multi-writer clobber (F862). It writes to `height` after erosion, overwriting erosion results.
- The fractal-subdivision approach works perfectly with our analytical base layer: evaluate the erosion filter to get base height, then apply coastline as a **mask** (not a height writer) that defines land/sea boundary. The fractal edge adds natural coves, peninsulas, and headlands.
- Coastline mask feeds into: material selection (sand/rock/grass transition at shore), scatter rules (no trees in water), and the water surface mesh placement.

### 8.5 Perlin noise hash optimization (Miles Oetzel)

**Article:** [Making Perlin Noise 30% Faster](https://milesoetzel.substack.com/p/making-perlin-noise-30-faster)

Linear hash with non-linear correction: compute 1 corner hash, derive 7 others with ADD (exploiting linearity), apply `hash * ((hash ^ 203663684) >> 16)` to kill periodicity. Plus IEEE 754 bit-hacking for gradient vectors. ~30% speedup on the foundational noise primitive.

**Integration path:** Our `_PermTableNoise` uses a permutation-table hash. When porting to the analytical filter (which calls noise thousands of times per point across octaves), swap to the linear hash. Quality tradeoffs vanish under domain warping + fBm stacking.

## 9. Synthesis: the complete technique stack for AAA terrain

Combining all references into a layered architecture:

```
Layer 0 — Base height:
  FractalNoise(x, z, seed) with Oetzel hash optimization
  + ErosionFilter(runevision analytical, per-point)
  → height + ridgeMap + analytical gradient
  PROPERTIES: world-coherent, chunk-parallel, deterministic

Layer 1 — Simulation refinement (optional, per hero node):
  Pipe-model hydraulic erosion (Mei/Decaudin) on overlapping regions
  + Thermal erosion with multi-material layering (soillib pattern)
  + Discharge-dependent erosion (soillib discharge^0.4 formula)
  → refined height + sediment map + discharge map
  PROPERTIES: needs overlap halo, runs once per hero node, not chunk-parallel

Layer 2 — Feature extraction:
  Flow accumulation (soillib stochastic Monte Carlo)
  + Stream order (Strahler from flow accumulation)
  + Coastline mask (fractal subdivision)
  + Sediment capacity C = Kc·sin(α)·|v| (Mei/Decaudin)
  → river network + coastline + material capacity map

Layer 3 — Material assignment:
  Slope-threshold scatter: dot(normal, up) → rock/stairs/gravel/grass
  Triplanar + persistent cliff noise (Reddit gHx4)
  Splatmap from sediment capacity + ridge map + slope
  → world-space-coherent materials, seamless across tiles

Layer 4 — Hero geometry (per-node):
  Cliff mesh builder, cave volume carver, waterfall 3D mesh
  Applied as delta * smoothstep(dist_from_edge / guard_width)
  → nodes plug together like puzzle pieces

Layer 5 — Scatter + vegetation:
  Ridge map → river placement (trace darkest creases)
  Slope threshold → rock/grass/stairs instancing
  Path network (A* on heightfield) → stairs emerge at steep+path intersection
  → populated terrain
```

Each layer feeds the next. No layer overwrites the previous — they compose additively or via masks. The analytical base (Layer 0) guarantees cross-tile continuity. Hero modifications (Layer 4) fade to zero at tile boundaries.

## 9b. Missed implementation details (deep re-read of all sources)

These are specific algorithmic techniques buried in the source code and papers that didn't make it into the high-level synthesis. Each one solves a specific bug or quality gap.

### From lpmitchell/AdvancedTerrainErosion source code:

1. **Per-pixel parameter overrides for biome blending.** The `Sample()` method accepts BOTH a config struct AND per-pixel overrides: `erosionStrength, erosionGullyWeight, erosionDetail, erosionRounding, erosionOnset, erosionAssumedSlope`. At biome boundaries, lerp these parameters between adjacent biome configs. Two tiles with different biomes produce smooth transitions without any stitching — the erosion filter itself handles the blend. Our terrain YAML contract must expose per-biome ErosionConfig.

2. **AssumedSlope parameter.** `gullySlope = lerp(actual_slope, actual_slope/|actual_slope| * assumedSlope.x, assumedSlope.y)`. When `assumedSlope.y > 0`, the filter acts as if terrain is steeper than it really is. Critical for flat biomes (deserts, plains) where you still want visible erosion gullies. Without this, flat terrain gets zero erosion detail.

3. **Rounding vec4 — separate ridge vs crease control.** `rounding.x` = crease rounding, `rounding.y` = ridge rounding, `rounding.z` = scale, `rounding.w` = per-octave decay. This is how you get sharp ridges + smooth valleys (or vice versa). A dark fantasy world wants sharp ridges and deep V-shaped creases — set `rounding.x` low, `rounding.y` low, `rounding.z` high.

4. **Onset vec4 — slope activation per feature type.** `onset.x` = initial slope gate, `onset.y` = per-octave slope gate, `onset.z` = ridge-map slope gate, `onset.w` = ridge-map per-octave gate. Controls when erosion features "turn on" relative to slope steepness. Low onset = erosion everywhere; high onset = erosion only on steep slopes.

5. **Normalization parameter in PhacelleNoise.** Controls how aggressively small-magnitude interpolated values are boosted. High normalization = crisp, uniform gullies. Low normalization = organic, varied intensity. Defaulting to ~0.4 gives good results.

6. **FadeTarget derivation.** `fadeTarget = clamp(h / (amplitude * 0.6), -1, 1)`. The 0.6 factor means the fade overshoots — valleys get pushed below -1 (clamped) and peaks above +1 (clamped). This creates a natural "flat bottom valleys, sharp peaks" character. Adjusting the 0.6 factor tunes the valley-to-peak ratio.

### From Mei/Decaudin pipe model:

7. **Flux scaling for stability.** If total outflow from a cell exceeds available water, ALL four fluxes are scaled down proportionally: `K = min(1, d·Δx²/(sum(f)·Δt))`. Without this, cells can go negative → simulation explodes. Our `_terrain_erosion.py` has no such limiter.

8. **Water-height gating in capacity.** The interactive implementation modifies capacity to `C = Kc·sin(α)·|v|·clamp(d, 0, 1)`. This prevents thin water films (d < 1) from dissolving bedrock at full rate. Physically correct — a 1mm rain layer shouldn't erode as much as a 1m river.

9. **Semi-Lagrangian advection for sediment transport.** Sediment at position `p` came from `p - v·Δt` (backtracking). Sample the source position with bilinear interpolation. This is numerically stable at large velocities (CFL-condition-free) unlike naive forward Euler which diffuses and oscillates.

10. **Velocity from flux differences, not finite-diff of height.** `u = (fL(x-1,y) - fL(x,y) + fR(x,y) - fR(x+1,y)) / (2·d_avg)`. The velocity is derived from the water flux field, not from height gradients. This gives coherent flow even in flat areas where height gradients are near-zero but water is still moving.

### From soillib CUDA kernels:

11. **Discharge^0.4 exponent.** `suspend = dt·ks·vol·slope·α·discharge^0.4`. This power-law relationship means a stream with 100x more discharge only erodes ~6.3x more. Prevents main rivers from over-carving while keeping tributaries active. Our code multiplies linearly by volume — no power-law.

12. **Exit slope threshold** (`exitSlope = 0.0075`). Particles terminate when local slope drops below this. Prevents wasted computation on flat terrain and stops over-erosion in valleys. Our droplets terminate only at array edges or max age — they wander forever on plains.

13. **Implicit Euler velocity integration.** `speed = speed/(1 + ds·(k1+k2)) + ds·k2·avg_speed/(1 + ds·(k1+k2))`. The `1/(1+ds·K)` damping is unconditionally stable at any timestep — no CFL condition. Our velocity update has no implicit damping.

14. **Bulk momentum averaging** (`avg_speed`). Each particle's velocity is influenced by the average velocity of all particles that passed through the same cell. This creates coherent flow channels — particles self-organize into streams. Our droplets are completely independent (no inter-particle communication).

15. **Multi-material thermal erosion.** When eroding: deplete sediment buffer first, then erode bedrock. When depositing: always add to sediment buffer. This creates realistic stratigraphy — exposed bedrock on steep slopes, sediment fill in valleys. Our thermal erosion operates on a single height channel.

### From Hesiod node list:

16. **Poisson blending (`blend_poisson_bf`).** Solves the Laplace equation to blend two heightmaps seamlessly — preserves interior gradients while matching boundary conditions exactly. Mathematically optimal for merging hero geometry patches into the base terrain. Potentially better than our smoothstep blend-weight for Layer 4 hero deltas.

17. **Accumulation curvature.** Computes curvature weighted by flow accumulation — valleys are concave where water concentrates, ridges are convex where water diverges. Our curvature is pure heightmap Laplacian (second-order finite differences), missing the flow-weighting that makes valleys look "scooped" and ridges look "pinched."

18. **Stratify node.** Creates visible geological strata (horizontal bands in cliff faces) by quantizing height into layers with different erosion resistance. Without this, cliffs look like smooth ramps. With it, cliffs show natural ledge-and-face patterns.

19. **Bulkify node.** Adds mass/volume to thin features — a ridge that's only 1 cell wide gets widened to be physically plausible. Prevents knife-edge artifacts from erosion filter.

### From the Perlin noise article:

20. **IEEE 754 gradient gap.** The bit-hack produces vectors in `[-1, -0.5] ∪ [0.5, 1]`, NOT uniform `[-1, 1]`. There's a dead zone around zero. Under fBm stacking this is invisible, but if sampling raw single-octave noise for feature placement, be aware gradients near zero are under-represented.

### AAA techniques not yet covered:

21. **Terrain holes / multi-layer heightmap.** For caves that open to the surface, overhangs, and arches — a single heightfield can't represent these. Need either (a) a second "ceiling" heightfield for overhangs, or (b) mesh-based cave volumes punched through the terrain with "terrain holes" (Unity Terrain has native hole support via TerrainData.SetHoles).

22. **Virtual texturing / terrain streaming.** At runtime, terrain textures are streamed at variable resolution based on camera distance. The splatmap resolution should be higher than heightmap resolution (typically 2x or 4x) for crisp material transitions.

23. **Terrain decals.** Roads, paths, scorch marks, blood pools — applied as projected decals on top of the terrain material, not baked into the splatmap. This allows dynamic terrain modification without re-baking.

24. **Normal map resolution.** Analytical normals from the erosion filter are per-vertex. For per-pixel detail, bake a normal map at 2x-4x heightmap resolution using the erosion filter's analytical derivatives. Combine with detail normals via Reoriented Normal Mapping.

## 10. Reddit r/proceduralgeneration Research Findings (R15 round)

### 10.1 Terrain erosion + node merging (R15D, R15I)

25. **Drainage-first river/lake generation.** Rivers are a consequence of drainage, not hand-drawn splines. Use elevation → flow direction → flow accumulation → depression filling to decide where rivers go, pits become lakes, steep drops become waterfalls. Our `_water_network` already does D8 flow — add depression filling/breach handling, then emit river corridor specs + lake polygons before any mesh pass. Sources: [Procedural Hydrology](https://nickmcd.me/2020/04/15/procedural-hydrology/), [r/proceduralgeneration rivers+lakes](https://www.reddit.com/r/proceduralgeneration/comments/pj90n1/)

26. **Discharge-driven meander, not sine noise.** Use discharge and momentum to make outer banks erode faster and inner banks deposit sediment. Replace our fixed `add_meander` sine wave with discharge/momentum-driven curvature so river width, bend radius, and bank asymmetry come from drainage strength. Source: [Meandering Rivers in Particle-Based Hydraulic Erosion](https://nickmcd.me/2023/12/12/meandering-rivers-in-particle-based-hydraulic-erosion-simulations/)

27. **Detect saddle first, carve second.** Mountain passes should be found by detecting low connections between massifs, then carved as corridors — not hoping noise produces a good pass. Use least-energy pathfinding between drainage basins. Sources: [r/proceduralgeneration massif post](https://www.reddit.com/r/proceduralgeneration/comments/1dbi5fe), [LayerProcGen cross-chunk pathfinding](https://runevision.github.io/LayerProcGen/)

28. **Vertical canyon walls via remap + terracing + cliff pass.** Reddit explicitly says: remap heightfield into near-vertical cliffs, add terracing, use a second cliff pass, or move to volumetric terrain. Hydrology-based carving produces deep ravines vs noise's "soft" valleys. Sources: [r/proceduralgeneration cliffs/overhangs](https://www.reddit.com/r/proceduralgeneration/comments/1rkfeba), [Hesiod](https://github.com/otto-link/Hesiod)

29. **Visible strata via ordered layer deposition + erosion.** Not "more noise" but deposit layers with different hardness, erode them, expose them on cliffs. Creates readable bands/terraces/hoodoos. Source: [geology-based terrain](https://www.reddit.com/r/proceduralgeneration/comments/174ox4o), [Purdue geological sculpting paper](https://www.cs.purdue.edu/cgvlab/www/publications/cordonnier2018sculpting/)

### 10.2 Water pipeline (R15F)

30. **Spline/ribbon river mesh from flow accumulation.** Derive width/depth from flow_accumulation, resample paths into splines, generate cross-sections, carve banks, triangulate lake shore polygons from basin cells. Source: [r/proceduralgeneration river gen](https://www.reddit.com/r/proceduralgeneration/comments/14jlnvt/)

31. **Baked flowmap textures.** Pack `RG=flow direction, B=foam` into a texture for Unity shader consumption. Arnklit Waterways is the reference: spline river mesh → baked flow/foam/distance maps → shader uniforms. Source: [Arnklit/Waterways](https://github.com/Arnklit/Waterways)

32. **Shoreline foam from signed distance field.** Derive shoreline foam from SDF around water boundaries × flow speed or wave steepness. Separate "wet edge" mask for rock darkening and soft alpha fade. Source: [r/gamedev low-poly water with foam](https://www.reddit.com/r/gamedev/comments/nvt7pq/)

33. **FFT ocean for large water only.** Multi-cascade FFT for oceans/seas with foam at breaking crests. For rivers and small lakes, keep spline/flowmap driven. Source: [r/gamedev FFT ocean tutorial](https://www.reddit.com/r/gamedev/comments/k7uiz9/)

### 10.3 Scatter + vegetation (R15H)

34. **Procedural UV unwrapping with Geometry Nodes.** Blender 3.3+ UV Unwrap node generates UV map islands procedurally from seam edges. Use for cliff meshes, debris, modular structures — stable texturing without hand-unwrapping. Source: [r/proceduralgeneration UV unwrapping](https://www.reddit.com/r/proceduralgeneration/comments/1sij0f4/), [GoodGood3D Patreon](https://www.patreon.com/goodgood3d), [Blender UV Unwrap node docs](https://docs.blender.org/manual/en/4.0/modeling/geometry_nodes/mesh/uv/uv_unwrap.html)

### 10.4 City generation (R15G)

35. **Terrain-flatten pass under buildings.** Reddit consensus: either flatten terrain under footprint with soft falloff, or avoid steep sites entirely. Our settlement_generator computes terrain-fit metadata AFTER placement but never mutates terrain. Need a flatten pass. Sources: [r/proceduralgeneration houses](https://www.reddit.com/r/proceduralgeneration/comments/159h41e), [r/proceduralgeneration village layout](https://www.reddit.com/r/proceduralgeneration/comments/1o25d1z)

36. **Terrain-cost road routing.** Tensor fields / hyperstreamlines from heightmaps or slope-weighted A* when terrain cannot be modified. Our MST is connectivity-first, not terrain-first. Sources: [r/proceduralgeneration tensor field roads](https://www.reddit.com/r/proceduralgeneration/comments/g22yhy), [r/proceduralgeneration road generation](https://www.reddit.com/r/proceduralgeneration/comments/1gfr2hp/)

### 10.5 AAA quality gap per generator (R15K Codex deep-dive)

Every generator in our codebase was graded. The pattern: **"good blockout / mask-generation logic, not ship-quality geometry."** The dominant issue is "simple primitive + isotropic noise + coarse material bands" vs AAA's "geologic cause-and-effect + hierarchical form breakup + authored silhouettes."

| Generator | AAA Grade | Key AAA Delta |
|---|---|---|
| `apply_morphology_template` | LOW | Templates are Gaussian blobs. Need drainage/lithology/tectonic controls. |
| `pass_cliffs / carve_cliff_system` | MID | Best-designed system conceptually. Hero insertion still a stub. Need stratified overhang meshes, fracture shelves, contact debris. |
| `pass_caves / carve_cave_volume` | LOW-MID | 5 archetypes good start. Cave path is random heading + sine. Need stress/water-driven branching, chamber reveals, roof-fall logic. |
| `generate_canyon` | LOW | Floor grid + two wall grids + noise. Need river incision, varying cross-sections by discharge, undercuts, slumped shelves. |
| `generate_waterfall` | LOW | Noisy cliff sheet + box ledges + circular pool. No water curtain mesh. Need plunge-pool erosion, splash shelves, mist-wet darkening. |
| `generate_cliff_face` | LOW-MID | Has overhang + ledge path. Need bedding planes, fracture networks, directional weathering. |
| `generate_swamp_terrain` | LOW | Flat noise + radial hummocks. Need drainage-derived micro-basins, organic channels, root heave, peat shelves. |
| `generate_natural_arch` | MID | Readable silhouette. Need asymmetry, notch erosion, partial collapse, contact rubble. |
| `generate_geyser` | MID | Concentric rings clear. Need downhill-biased terracing, overflow asymmetry, heat damage staining. |
| `generate_sinkhole` | MID | Annular rim readable. Need broken rim segments, shelf failures, tilted collapse slabs, seep paths. |
| `generate_lava_flow` | MID | Spline ribbon useful. Need slope response, branching lobes, pressure ridges, cooled rafts. |
| `generate_ice_formation` | LOW-MID | Basic cones + noise. Need drip-line clustering, fracture patterns, thickness-driven materials. |

**What Horizon / God of War / Elden Ring do differently:**
- **Horizon:** Watersheds, drainage basins, erosion corridors, lithology-driven cliff bands → then rock kits + scan-backed materials.
- **God of War:** Art-direct for combat camera + traversal readability. Ledges/overhangs/caves placed where encounters need them.
- **Elden Ring:** Asymmetry, silhouette drama, environmental storytelling. Broken shelves, hidden paths, ruin adjacency, oppressive occlusion.
- **All three:** Procedural masks + blockout → authored sculpting, kitbashing, decals, layered materials, scan detail, hero-mesh replacement. That last stage is our main missing piece.

### 10.6 Wiring gaps — 32 functions with zero production callers (R15J)

These functions exist but are never called from the terrain pipeline:
- `generate_biome_transition_mesh`, `generate_waterfall_mesh`, `generate_terrain_bridge_mesh` (mesh generators)
- `apply_differential_erosion` (stratigraphy)
- `generate_braided_channels`, `detect_estuary`, `detect_karst_springs`, `detect_perched_lakes`, `apply_seasonal_water_state` (water)
- `apply_morphology_template` (30 templates)
- `compute_height_blended_weights` (materials)
- `detect_destructibility_patches`, `compute_footprint_surface_data` (gameplay)
- `apply_edit` (terrain_live_preview)
- `generate_weathering_timeline`, `apply_weathering_event` (weathering)
- `generate_diff_overlay` (visual diff)
- Plus 15 more (see R15J full report)

**Implementation impact:** Wiring these into the pipeline is often a 1-line change per function. The functions are written, tested, and ready — they just have no caller in the pass DAG or compose_* orchestrators.

## 11. Codex R16 Research Round (2026-04-12) — 6 gpt-5.4 agents

### 11.1 Cliff Generation Best Practices (R16A)
**Key insight:** Real cliffs are NOT heightmap slopes — they need a second geometry pass layered on top.
- Cliff faces need visible rock strata (bedding planes with different erosion resistance)
- Overhangs from differential erosion of soft layers under hard caprock
- Talus/scree fields accumulate at angle of repose at cliff base
- Cliff vegetation (hanging moss, grass tufts) placed by Distribute Points on Faces with slope/moisture filter
- Tiny Glade approach: procedural geometry layered on coarse terrain surface, not heightfield manipulation
- Blender Geometry Nodes cliff workflow: extrude + noise displacement + material index per stratum
- **VeilBreakers implementation:** Task 6.82 (cliff mesh builder with strata), Task 6.110 (geological stratification), Task 9.17 (natural arch upgrade)

### 11.2 Terrain Material Best Practices (R16B)
**2024-2026 consensus stack:** height-based layer blending + selective triplanar on cliffs + macro/micro variation + stochastic tiling + wetness as overlay layer
- **Height-based splatmap:** Use Mask Map B channel in Unity URP. Stock Terrain Lit limited to 4 layers for height behavior; custom shader needed for >4
- **Triplanar:** Selective use only — cliffs, steep slopes, UV-less meshes. 3x texture samples = slower. Profile on target hardware (Reddit r/gamedev March 2025)
- **POM:** Niche close-range effect, not terrain-wide. Triplanar+POM needs custom view-vector handling (Reddit r/unrealengine Oct 2024)
- **Macro variation:** Second larger-scale sample modulating color/roughness. Strongest anti-repetition after stochastic tiling
- **Stochastic tiling:** UnityLabs procedural-stochastic-texturing, Unity TilingRandomization. Watch for normal-map edge artifacts
- **Wetness:** Separate overlay/modifier layer, not duplicate materials. Paintable wetness reusing underlying PBR
- **Blender materials:** Node-driven from Musgrave variants (Hetero Terrain, Hybrid Multifractal, Ridged Multifractal) + color ramps
- **Sources:** Reddit r/Unity3D, r/unrealengine, r/gamedev 2024-2026; Unity URP docs; UnityLabs stochastic texturing repo
- **VeilBreakers implementation:** Tasks 7.4 (triplanar), 7.17-7.21 (height blending, selective triplanar, stochastic, wetness overlay, Blender material stack)

### 11.3 Blender Terrain Tools (R16C)
- Terrain Mixer as primary Blender-side authoring fallback
- A.N.T. Landscape for procedural blockouts
- SRTM Terrain Importer for real-world reference data
- Geometry Nodes UV Unwrap node (3.3+) for procedural UV
- Our existing addon_toolchain.py already registers these correctly

### 11.4 AAA Studio Tool Comparison (R16D)
**Professional pipelines are hybrid, not single-tool:**
- **World Machine:** Base heightfields, erosion, masks, engine-ready exports. Hurricane Ridge: faster erosion, repeatable output, map-driven params, tiled builds, CLI automation
- **Gaea 2.0-2.2:** GPU processing, Build Swarm, Regions, Unreal/Houdini bridges. Studios: Weta FX, Remedy, Respawn, Ubisoft, Sony Santa Monica
- **Houdini:** Pipeline backbone. HeightField Erode 3.0: hydraulic+thermal, multiscale chaining, auxiliary layers (sediment/debris/flow). HDAs for Unreal/Unity
- **UE 5.5:** Terrain HOST, not simulator. Landscape + Nanite + World Partition + PCG
- **Unity 6:** Terrain Tools 5.3.x package iteration. heightmap/splatmap import, sculpting, multi-detail scatter
- **Critical features every terrain tool must have:**
  1. Non-destructive procedural authoring (graph-based, reproducible)
  2. High-quality multiscale erosion with deterministic output
  3. Large-world support (tiling, regions, partial rebuilds, streaming export)
  4. Automation and reproducibility (CLI, batch, farm-friendly)
  5. Rich auxiliary outputs (masks, splatmaps, flow/sediment/debris layers)
  6. Strong engine interop (correct resolution/scale/masks in Unreal/Unity)
  7. Performance at 8K+ production resolutions
- **Our toolkit's niche:** Orchestration layer + studio-specific workflow. Use external solvers for geology, engine-native for streaming/scatter/runtime
- **VeilBreakers implementation:** Tasks 9.23-9.26 (determinism, multiscale erosion, auxiliary output validation, 8K performance)

### 11.5 Terrain Streaming & LOD (R16E)
- **Quadtree/CDLOD still canonical** — Strugar 2010 quadtree variant with smooth transitions + distance-based detail
- **Geometry clipmaps** (Hoppe 2004) — nested regular grids around viewer, incremental refill on camera move
- **Terrain holes for caves:** Unity Paint Holes + mesh proxy. Holes affect lighting, physics, NavMesh
- **Unity streaming:** Addressables LoadSceneAsync for additive background loading of terrain tiles
- **Runtime deformation:** SetHeightsDelayLOD + CopyActiveRenderTextureToHeightmap + DirtyHeightmapRegion for footprints/impacts
- **Horizon Zero Dawn:** Player-centric streaming, predictive loading, LOD bias by distance. Meshes for all vertical complexity
- **Elden Ring:** Cell-based world streaming (CEDEC 2022), terrain as broad landform with mesh overlays
- **AAA consensus:** Heightfields for broad landforms, meshes for cliffs/caves/arches/vertical complexity
- **VeilBreakers implementation:** Tasks 8.12-8.18 (streaming, virtual texturing, flowmaps, deformation, holes, CDLOD, collision)

### 11.6 Reddit r/proceduralgeneration Top Posts (R16F)
Research captured top community patterns — key techniques already mapped to tasks above.

## 12. Quality Testing & Agent Guardrails Research (2026-04-12)

### 12.1 Current Quality Gaps (from Opus QA1 test suite audit)
**CRITICAL:** The existing 7-layer defense catches code structure bugs but has ZERO visual quality gates.
- No geometric quality tests (manifold, normals, degenerate faces) — nowhere in test suite
- No statistical distribution tests (fractal dimension, slope distribution, height histogram shape)
- No drainage connectivity tests (rivers tested for adjacency but NOT that water flows downhill)
- No erosion result quality tests (only "something changed", not "V-shaped valleys formed")
- No cross-feature integration tests (waterfall+cliff, cave+cliff untested)
- No LOD fidelity tests (resolution downsample but no visual quality metrics)

### 12.2 Proposed Quality Layers (L7-L10)
- **L7 Geometry Gate:** bmesh validation after every mesh generation (is_manifold, calc_area, normals)
- **L8 Visual Regression:** pHash + SSIM screenshot comparison against golden references
- **L9 Statistical Shape:** K-S test on height distribution, fractal dimension [2.1-2.5], slope histogram chi²
- **L10 Agent Pre/Post Flight:** Mandatory baseline recording + regression check for every edit

### 12.3 Blender Geometry Validation API
Key bmesh properties: `BMEdge.is_manifold`, `BMFace.calc_area()`, `BMEdge.calc_length()`, `BMVert.is_wire`
Key repair ops: `bmesh.ops.dissolve_degenerate()`, `bmesh.ops.remove_doubles()`, `bmesh.ops.recalc_face_normals()`
Reference: Blender 3D Print Toolbox addon — production-grade mesh validation

### 12.4 Visual Regression Thresholds
- pHash distance > 0.15: flag for review
- SSIM < 0.80: automatic failure
- SSIM 0.80-0.92: warning, require visual inspection
- SSIM > 0.92: pass

### 12.5 Statistical Terrain Quality Thresholds
- Fractal dimension: 2.1-2.5 for natural terrain (< 2.05 = too smooth, > 2.5 = noise)
- Drainage density: > 0.02 for mountains (< 0.01 = no visible drainage)
- Cliff fraction: > 5% for canyon/volcanic (< 5% = no real cliffs)
- Height entropy: > 2.0 (< 2.0 = effectively flat)

### 12.6 Agent Execution Quality Protocol
Created: `.planning/AGENT_QUALITY_PROTOCOL.md` (340 lines)
- 6-step pre-edit protocol (brief_agent, channel contract, test coverage, findings, baselines, checklist gate)
- 8-step post-edit protocol (lint, tests, substance, imports, channels, statistics, reviewer, checklist gate)
- Visual verification protocol (which edits require visual QA, viewport settings, pass/fail criteria)
- Rollback protocol (revert triggers, fix-forward triggers, git procedures)
- Quality escalation (8 triggers, structured format, do-NOT-escalate list)
- Multi-agent coordination (file ownership, verification gate, naming convention)

### 12.7 Implementation Tasks
All mapped to Phase 10 tasks 10.9-10.34 in EXECUTION_PLAN.md. Key additions:
- 6 new test categories (geometric, statistical, physical, cross-feature, LOD, export)
- Visual regression infrastructure (QA renderer, golden compare, CI gate)
- Quality lint extensions (4 new patterns)
- Pre-commit hook enforcement

## 13. AAA Studio QA Processes (Opus QA3 Research, 2026-04-12)

### 13.1 Key Studio Practices
- **AC Origins:** Daily automated world validation scanning entire map for data integrity. Visual reports to creation team. Caught regressions automatically.
- **Far Cry 5:** GPU compute pipeline + Houdini rule sets constraining procedural output to valid ranges. Cliff displacement validated against gameplay traversal.
- **Witcher 3:** World Machine 46x46 tiles, hand-painted textures, procedural vegetation based on water accumulation + sunlight simulation.
- **Horizon Zero Dawn:** GPU compute placement with constraints built INTO the generator — impossible to produce invalid output by construction.
- **Townscaper:** Wave Function Collapse with adjacency constraint validation at import time — bad output is structurally impossible.

### 13.2 PTRM Realism Scoring
- Perceived Terrain Realism Metric (ACM 2022): scores 0.0-1.0
- >0.6 acceptable, >0.8 good
- Based on geomorphon classification (10 landform types) compared to real-world DEM reference

### 13.3 Key Thresholds from AAA Research
- Geomorphon types: >= 5 of 10 types present for landscape diversity
- Slope histogram KL-divergence from reference: < 0.3
- Drainage path continuity: 100% (no uphill segments unless intended lakes)
- SSIM vs golden: > 0.95 pass, < 0.85 fail
- Poly budget: 10K-100K tris per terrain chunk

### 13.4 Sources
- [Far Cry 5 Procedural World (GDC 2018)](https://www.gdcvault.com/play/1025557/)
- [AC Origins World Validation (GDC 2018)](https://gdcvault.com/play/1025452/)
- [Witcher 3 Landscape (GDC 2014)](https://www.gdcvault.com/play/1020197/)
- [Horizon Zero Dawn GPU Placement (GDC 2017)](https://www.gdcvault.com/play/1024700/)
- [PTRM Paper (ACM 2022)](https://dl.acm.org/doi/10.1145/3514244)
- [VideoGameQA-Bench (NeurIPS 2025)](https://arxiv.org/abs/2505.15952)
- [pytest-blender](https://github.com/mondeja/pytest-blender) — headless Blender testing
- [Hypothesis](https://hypothesis.readthedocs.io/) — property-based testing

## 14. Sources (continued)

- runevision, [Fast and Gorgeous Erosion Filter](https://blog.runevision.com/2026/03/fast-and-gorgeous-erosion-filter.html) — the video/article this synthesis is built on.
- runevision, [LayerProcGen](https://runevision.github.io/LayerProcGen/) — chunk-parallel generation library, companion to the filter.
- Job Talle, [Simulating hydraulic erosion](https://jobtalle.com/simulating_hydraulic_erosion.html) — reference droplet algorithm (what we should stop doing). Note: uses `vx = friction*vx + normal.x*speed` — purely slope-direction acceleration, no `+Δh·g` term. Confirms our F277 sign bug.
- Nick McDonald, [Procedural Hydrology](https://nickmcd.me/2020/04/15/procedural-hydrology/) — dynamic lake/river simulation, reference for the ridge-map-to-river step.
- [terrain-erosion-3-ways](https://github.com/dandrino/terrain-erosion-3-ways) — three canonical erosion implementations for comparison.
- [World Machine](https://www.world-machine.com/) — AAA industry baseline; our target quality bar.
- Mei/Decaudin/Hu, [Fast Hydraulic Erosion Simulation on GPU](https://inria.hal.science/inria-00402079/document) — pipe-model shallow water erosion. Capacity formula `C = Kc·sin(α)·|v|`. Reference for hero-node refinement.
- [erosiv/soillib](https://github.com/erosiv/soillib) — CUDA geomorphology library. Discharge-dependent erosion, multi-material thermal, stochastic flow accumulation.
- [otto-link/Hesiod](https://github.com/otto-link/Hesiod) + [HighMap](https://github.com/otto-link/HighMap) — 289-node terrain tool. Reference architecture for operation completeness.
- [lpmitchell/AdvancedTerrainErosion](https://github.com/lpmitchell/AdvancedTerrainErosion) — Burst C# port of runevision's filter. Drop-in Unity UPM package.
- Miles Oetzel, [Making Perlin Noise 30% Faster](https://milesoetzel.substack.com/p/making-perlin-noise-30-faster) — linear hash + bit-shift correction, IEEE 754 gradient vectors.
- [Coastline Paradox Part Two](https://www.reddit.com/r/proceduralgeneration/comments/1r0zfva/the_coastline_paradox_part_two_how_to_generate/) — fractal coastline subdivision.
- [Interactive Erosion Simulator](https://huw-man.github.io/Interactive-Erosion-Simulator-on-GPU/) — WebGL implementation of Mei/Decaudin pipe model with source.
