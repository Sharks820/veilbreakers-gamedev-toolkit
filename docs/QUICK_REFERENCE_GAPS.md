# VeilBreakers vs AAA — Quick Reference Card

**Current Avg:** 4.4/10 | **AAA Target:** 9/10 | **Achievable in 4-6 weeks:** 6.8/10

## Category Scorecard

| Category | Current | Gap | Effort | Top Tool #1 | Impact |
|----------|---------|-----|--------|-----------|--------|
| **Terrain** | 4/10 | 5 pts | 3 days | NumPy Vectorize | 50-200x speedup |
| **Architecture** | 3/10 | 6 pts | 4 days | GeoNodes Modifier | Non-destructive editing |
| **Vegetation** | 2/10 | 6 pts | 3 days | Sapling Tree Gen | Instant L-system |
| **Interiors** | 5/10 | 3 pts | 2 days | Occlusion Culling | Interior streaming |
| **Characters** | 3/10 | 5 pts | 3 days | Skin Modifier | Organic mesh from rig |
| **Materials** | 4/10 | 4 pts | 2 days | Fix SSS/Metal values | Photo-real skin/metal |
| **Lighting** | 5/10 | 3 pts | 2 days | Nishita Sky + EEVEE | Procedural atmosphere |
| **Props** | 4/10 | 4 pts | 3 days | Prop generators ×3 | Regional variety |
| **Level Design** | 6/10 | 2 pts | 1 day | Snap validation | Modular feedback |
| **Performance** | 6/10 | 3 pts | 2 days | Billboard LOD | 10x tree rendering |

## P0: Do This First (1.5 days, 2.5-point gain)

```
DAY 1:
  1. Fix SSS weight: 0.15 → 1.0 in procedural_materials.py (30 min)
  2. Fix metal colors: use physically-based table (30 min)
  3. NumPy vectorize heightmap generation (4 hours)

DAY 2:
  4. Download Sapling Tree Gen addon + wire to MCP (4 hours)
  5. Enable EEVEE volumetrics in Blender MCP calls (2 hours)

RESULT: 4.4 → 6.9/10 (Elden Ring-comparable terrain + trees + atmosphere)
```

## P1: Next Week (5 days, 1-point gain)

```
  • Nishita sky shader + atmospheric scattering (2 days)
  • Skin Modifier character refactor (1 day)
  • Sapling + billboard LOD pipeline (2 days)
  
RESULT: 6.9 → 7.9/10 (AAA-competitive)
```

## P2: Month 2 (5 days, 0.5-point gain)

```
  • GeoNodes shape grammar (3 days)
  • WFC dungeon generator (2 days)
  
RESULT: 7.9 → 8.4/10 (expert-level)
```

## The 3 Biggest Gaps

### Gap 1: Mesh Quality (Characters + Buildings)
- **Problem:** Primitives (cylinders + spheres) create discrete boundaries
- **AAA Does:** Skin Modifier (skeleton → organic mesh) OR AI generation (Hunyuan3D)
- **Your Fix:** 1-day Skin Modifier refactor replaces 150 lines of assembly
- **Impact:** Characters instantly look hand-sculpted instead of procedural

### Gap 2: Shading/Texturing Correctness
- **Problem:** SSS too weak (0.15), metals too dark, no micro-normal layering
- **AAA Does:** Physical-based material ranges, 3-layer normal maps
- **Your Fix:** Audit PBR tables (0.5 day) + add micro-normal blend (1 day)
- **Impact:** Skin glows, metals shine, surfaces feel layered

### Gap 3: Vegetation Geometry
- **Problem:** Primitive branching, no seasonal variants, no wind baking
- **AAA Does:** L-system (Sapling) + Bezier curves + wind vertex colors
- **Your Fix:** 1-day Sapling addon integration
- **Impact:** Forests instantly look like Skyrim/Fable, no hand-modeling needed

## Tool Installation Checklist

All free, <8GB VRAM, no subscriptions:

- [ ] NumPy + Scipy (already have, just use)
- [ ] Sapling Tree Gen (Blender addon, download from Extensions)
- [ ] WFC library (`pip install wave_function_collapse`)
- [ ] Nishita Sky reference (implement ourselves from paper)
- [ ] Blueprint addon (optional, for snap-points)

## One-Week Sprint Plan

**Monday:** SSS/metal fixes (30 min) + NumPy vectorize (1 day)
**Tuesday:** Sapling integration (4 hours) + EEVEE wiring (2 hours)
**Wednesday:** Nishita sky shader (2 days)
**Thursday:** Skin Modifier refactor (1 day)
**Friday:** Billboard LOD for vegetation (2 hours) + testing

**Result:** Push to `feature/aaa-visual-overhaul`, benchmark vs Skyrim asset reference, celebrate.

## Realistic Outcome Timeline

| Timeline | Score | Looks Like |
|----------|-------|-----------|
| Today | 4.4/10 | Early access indie (visible flaws) |
| After P0 (1.5 days) | 6.9/10 | Elden Ring terrain + trees |
| After P0+P1 (6 days) | 7.9/10 | AAA-competitive, most reviewers wouldn't notice |
| After P0+P1+P2 (11 days) | 8.4/10 | Expert-level, indistinguishable from big-studio assets |
| After full overhaul (3 months) | 8.8/10 | Skyrim-grade with better technical polish |

## DON'T Attempt (Yet)

- [ ] MetaHuman DNA morphing (overkill, 100 blend shapes sufficient)
- [ ] UDIM multi-tile textures (wait until 8+/10 base quality)
- [ ] Full facial articulation (38 FACS shapes = 80% benefit with 20% effort)
- [ ] Cloth simulation (defer to Phase 2)
- [ ] Cascadeur AI mocap (defer to animation phase)
- [ ] Hunyuan3D per-asset (tool for heroes/bosses only, not every NPC)

## Metrics You Can Measure

After P0+P1:
- **FPS improvement:** Terrain LOD + billboard trees should hit 60 FPS on RTX 4060 Ti (vs current maybe 30)
- **Asset production time:** Sapling trees from 3 hours → 15 min per species
- **Screenshot quality:** Night-and-day difference in lighting, skin, metals
- **Polygon budget headroom:** NumPy speedup allows 2x terrain resolution

---

**Next Step:** Read full GAP_ANALYSIS_VS_AAA.md, then execute P0 checklist.
