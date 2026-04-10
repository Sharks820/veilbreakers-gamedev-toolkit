# Phase 43: Geometry Quality Overhaul -- Weapons, Armor, Creatures - Research

**Researched:** 2026-04-04
**Domain:** Procedural mesh generation algorithms for dark fantasy game assets (pure Python, MeshSpec pattern)
**Confidence:** HIGH

## Summary

Phase 43 addresses the single most impactful visual quality gap in the toolkit: every weapon, armor piece, and creature currently scores PLACEHOLDER or BASIC on visual verification. The root cause is insufficient vertex density combined with overly simple geometric construction. Swords have 586 verts (target: 2000-4000), axes have 297 verts (target: 1500-3000), armor pieces have 280-350 verts (target: 1500-5000), and creatures have 1530-2550 verts (target: 5000-15000 for LOD0). All assets have ZERO materials applied. The creature generators additionally suffer from orientation bugs (wolf upside-down) and 5 out of 7 creature part generators crash with a tuple error.

The generators already follow the correct architectural pattern: pure Python functions returning MeshSpec dicts (vertices, faces, uvs, metadata), merged from component parts (blade + guard + grip + pommel). The problem is not the architecture but the **detail density within each component**. Blades use 10-14 cross-section rings where 30-50 are needed. Guards use simple box/torus primitives where shaped profiles with filigree detail are needed. Grips use 10-12 rings where 20-30 with wrap indentation are needed. Creatures use 12-16 cross-section segments where 24-40 are needed.

**Primary recommendation:** Rewrite the internal component builders (_build_cross_section_blade, _build_ergonomic_grip, _build_cross_guard, _build_pommel, etc.) to increase segment counts 3-5x, add secondary detail geometry (fuller grooves with proper depth, guard quillons with shaped ends, pommel facets, finger articulation for gauntlets), and wire the existing procedural material library post-generation. Do NOT change the MeshSpec return format or the QUALITY_GENERATORS registry -- the API contract stays the same, only the internal geometry density increases.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GEOM-01 | Weapon geometry redesign -- 3-10x more verts, proper blade/guard/pommel silhouettes | Verified: current counts 297-586 verts, target 1500-4000. Cross-section segment increases from 10-14 to 30-50, plus sub-component detail. See Architecture Patterns Section 1. |
| GEOM-02 | Armor anatomical fit + layered plate detail + articulated fingers on gauntlet | Verified: current counts 281-347 verts, target 1500-5000. armor_meshes.py has 12 slot types but low detail. See Architecture Patterns Section 2. |
| GEOM-03 | Creature anatomy overhaul -- musculature, skeletal deformation zones, proper proportions | Verified: current 1530-2550 verts, target 5000-15000. Spine-profile approach is correct but needs 2-3x segment density. Orientation bugs (wolf upside-down) and 5 crashed part generators (tuple error). See Architecture Patterns Section 3. |
| TEST-03 | Visual regression -- zai before/after for each generator category | Test infrastructure: test_weapon_quality.py (44+ tests), test_creature_anatomy.py (exists but import error). Need to update min_verts assertions and add new detail validation tests. |
| TEST-04 | Opus verification scan after every phase -- follow-up rounds until CLEAN | Standard workflow requirement. Each generator must produce visual output for zai scoring. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export. Do not skip steps.
- **Always verify visually** after Blender mutations via `blender_viewport` action=`contact_sheet`.
- **Use seeds** for reproducible generation.
- **Batch when possible**: use `asset_pipeline` action=`batch_process`.
- **Game readiness**: Run `blender_mesh` action=`game_check` before export.
- **All code is pure Python with math-only dependencies** (no bpy/bmesh in generator files). bpy usage only in handlers/__init__.py via `_build_quality_object()`.
- **MeshSpec return format is the API contract** -- must maintain compatibility with existing test suite and handler dispatch.
- **Bug scan rounds until CLEAN** -- never stop after one round if issues found.
- **Dark fantasy visual standard**: FromSoftware / Bethesda quality bar.
- **Blender is Z-up** -- systemic recurring bug where code uses Y for vertical.

## Standard Stack

### Core (No new dependencies -- pure Python math generators)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `math` | 3.13 | Trig, interpolation, geometry math | Only dependency allowed in MeshSpec generators |
| `functools.lru_cache` | 3.13 | Cached trig tables for repeated segment angles | Already used in procedural_meshes.py |

### Supporting (Existing toolkit components to wire)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `weapon_quality.py` | 3090 lines | Primary weapon/armor generator file | REWRITE internals, keep API |
| `creature_anatomy.py` | 3003 lines | Creature generators (quadruped, fantasy, parts) | REWRITE internals + fix crashes |
| `armor_meshes.py` | 2246 lines | 12-slot armor system, 52 style variants | REWRITE internals for density |
| `monster_bodies.py` | 1859 lines | Brand-feature system for monsters | Fix weld bug, increase density |
| `equipment.py` | 2214 lines | Legacy weapon generators (bmesh-based) | REPLACE with weapon_quality calls |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual vertex placement | Subdivision surface + displacement | Would require bpy (not pure Python) -- breaks architecture |
| Increasing segment counts | Tripo AI for all weapons | Slow ($0.10-0.25/model), non-deterministic, needs post-processing |
| Pure math generators | bmesh boolean operations | Requires Blender runtime, breaks pure Python pattern |

## Architecture Patterns

### Current File Structure (no changes needed)
```
Tools/mcp-toolkit/blender_addon/handlers/
  weapon_quality.py        # 9 generators: sword/axe/mace/bow/shield/staff/pauldron/chestplate/gauntlet
  creature_anatomy.py      # 7 generators: quadruped(7 species)/fantasy(chimera)/mouth/eyelid/paw/wing/serpent
  armor_meshes.py          # 12 slots x ~5 styles = ~52 generators
  monster_bodies.py        # 6 body types x 10 brands
  procedural_meshes.py     # 40+ additional weapon types (greatsword, curved_sword, etc.)
  equipment.py             # Legacy bmesh generators (to be deprecated)
```

### Pattern 1: Cross-Section Ring Extrusion (Weapons)
**What:** Build blades/shafts by defining cross-section profiles and extruding along a spine curve.
**Current problem:** Only 10-14 rings with 8-10 verts per ring. Need 30-50 rings with 12-16 verts per ring.
**Target vertex budgets:**

| Weapon | Current Verts | Current Tris | Target Verts | Target Tris | Key Detail Additions |
|--------|--------------|-------------|-------------|-------------|---------------------|
| Sword | 586 | 1108 | 2000-3000 | 3500-5500 | 40+ blade sections, 16-vert cross-section, shaped guard quillons, filigree pommel, leather wrap indentation |
| Axe | 297 | 560 | 1500-2500 | 2800-4500 | 3D wedge head (not pancake), beard curve, poll detail, hafting wedge |
| Mace | 462 | 832 | 2000-3000 | 3600-5400 | Flanges with proper thickness+taper, morningstar spike geometry, head facets |
| Bow | 356 | 664 | 1500-2500 | 2800-4500 | Curved limb tapering, riser shelf, nocking point, real string geometry |
| Shield | 360 | 704 | 2000-3500 | 3600-6500 | Boss dome, rim lip, heraldry relief, back grip/enarmes, correct scale (1.0m not 0.5m) |
| Staff | 330 | 624 | 1500-2500 | 2800-4500 | Gnarled bark texture geometry, orb cage with crystal, wrapped grip |

**Implementation approach:**
```python
# BEFORE: 14 sections, 10 verts per ring = 140 blade verts
num_sections=14, vpr=10

# AFTER: 40 sections, 14 verts per ring = 560 blade verts
# Plus: ricasso section (6 extra rings), fuller groove depth, blood channel,
# spine ridge, edge bevel with 2-step profile
num_sections=40, vpr=14
# Additional detail rings at guard junction (+8 rings)
# Tip refinement with 4 tapered rings (+4 rings)
```

### Pattern 2: Anatomical Profiling (Armor)
**What:** Build armor pieces around standardized body reference points with layered plate geometry.
**Current problem:** Simple curved plates with 240-297 faces. Need articulated segments, rivet detail, edge lips.
**Target vertex budgets:**

| Armor | Current Verts | Target Verts | Target Tris | Key Detail Additions |
|-------|--------------|-------------|-------------|---------------------|
| Pauldron | 289 | 1500-2500 | 2800-4500 | Multi-plate layers, rivet bumps, edge lip, shoulder curve matching |
| Chestplate | 347 | 2500-4000 | 4500-7200 | Anatomical contour (pectorals, abs), plate seam lines, gorget connection |
| Gauntlet | 281 | 2000-3500 | 3600-6300 | 5 articulated fingers (4 joints each), cuff flare, knuckle plates |

**Implementation approach:**
```python
# Gauntlet: articulated fingers
# Each finger: 4 segments x 8-vert cross-section = 32 verts
# 5 fingers: 160 verts just for digits
# Palm plate: 16x8 grid = 128 verts
# Cuff: 20 rings x 12 verts = 240 verts
# Knuckle guard: 80 verts
# Total: ~600-800 verts for hand + 400-600 for cuff
```

### Pattern 3: Spine-Profile Extrusion (Creatures)
**What:** Define anatomical spine curves with varying elliptical cross-sections. Already implemented in creature_anatomy.py.
**Current problem:** Low segment counts (12-16 cross-section segments) produce smooth tubes instead of muscular forms. Need anatomical landmarks.
**Target vertex budgets:**

| Creature | Current Verts | Target Verts | Target Tris | Key Detail Additions |
|----------|--------------|-------------|-------------|---------------------|
| Wolf | 2278 | 6000-10000 | 11000-18000 | Rib cage bulge, shoulder blade peaks, hip socket depressions, muzzle detail, ear cartilage, toe pads |
| Bear | 2518 | 8000-12000 | 14000-22000 | Massive shoulder hump, heavy paws, thick neck folds |
| Fantasy (chimera) | 2552 | 10000-15000 | 18000-27000 | Multi-head junctions, wing membrane grid, tail segments, brand features |
| Horse | 1530 | 6000-10000 | 11000-18000 | Barrel chest, fetlock joints, mane geometry, hoof detail |
| Deer | 1690 | 5000-8000 | 9000-14000 | Antler branching, thin legs with joint detail |

**Implementation approach:**
```python
# BEFORE: 12 cross-section segments, body produces ~800 body verts
cross_segments=12, spine_points=20

# AFTER: 24 cross-section segments, body with anatomical landmarks
cross_segments=24, spine_points=40
# Plus: muscle attachment ridge vertices at shoulder/hip
# Plus: rib cage undulation pattern
# Plus: detailed paw geometry (4 toes + pads + claws)
```

### Pattern 4: MeshSpec Assembly (Shared Pattern)
**What:** All generators return MeshSpec dicts assembled from component meshes via `_merge_meshes()`.
**Keep this pattern.** It enables:
- Per-component UV island mapping
- Per-component vertex group assignment
- Detail feature tracking in metadata
- Component-level quality metrics

### Anti-Patterns to Avoid
- **Changing the MeshSpec return format:** Tests and handler dispatch depend on the current dict structure. Add new metadata keys, never remove existing ones.
- **Using bpy/bmesh in generator functions:** The pure Python pattern enables headless testing without Blender. All 19,850+ tests run without Blender.
- **Global segment count constants:** Each weapon/armor/creature type needs different density. Use per-type presets, not global `DEFAULT_SEGMENTS`.
- **Uniform cross-sections:** Real weapons/anatomy have varying profiles. Use profile functions `f(t) -> (rx, rz)` not constant radii.
- **Forgetting Z-up in Blender:** Y-up bugs are systemic. Always verify: height is Z, forward is -Y or +Y depending on convention. Wolf upside-down bug is likely a Y/Z mixup.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Smooth interpolation between control points | Custom lerp code | `smootherstep()` utility (PIPE-06 creates this) | Already 35 sites needing replacement, use the shared utility |
| Material assignment post-mesh | Inline material code in generators | MATERIAL_LIBRARY (52 materials) + 6 procedural generators | Already exists, just not wired (MAT-01 phase 40 dependency) |
| UV unwrapping algorithms | Custom UV projection | Existing `_auto_generate_uvs()` in creature_anatomy.py, plus xatlas via blender_uv | Pure Python UV for testing, xatlas for production |
| Mesh validation | Custom face/vert checks | Existing `validate_mesh_spec()` in test_weapon_quality.py | Already validates indices, components, ranges |
| Trig lookup tables | Repeated math.cos/sin calls | Existing `_get_trig_table(segments)` in procedural_meshes.py | LRU-cached, eliminates redundant trig per segment count |

## Common Pitfalls

### Pitfall 1: Disconnected Component Junctions
**What goes wrong:** Blade floats above guard, guard floats above grip. Visible gaps at component boundaries.
**Why it happens:** Each component is built independently with its own coordinate origin. Merge offset calculation off by one segment.
**How to avoid:** Use explicit junction Y-coordinates shared between adjacent components. Blade base Y must equal guard top Y. Guard bottom Y must equal grip top Y. Verify with bounding box overlap checks.
**Warning signs:** `gap_visible` in zai analysis, vertices at component boundary don't share Y coordinates.

### Pitfall 2: Flat Silhouettes from Insufficient Cross-Section Vertices
**What goes wrong:** Sword blade looks like a flat rectangle, not a diamond/lenticular cross-section.
**Why it happens:** Cross-section ring has only 4-8 vertices, making any profile look polygonal.
**How to avoid:** Minimum 12 vertices per cross-section ring for weapons, 24 for organic creatures. Test: rotate view 90 degrees to check cross-section profile.
**Warning signs:** Asset looks correct from front but flat/blocky from side or top.

### Pitfall 3: Wolf Upside-Down / Orientation Bugs
**What goes wrong:** Creatures generate inverted, doors lie flat, shields are horizontal.
**Why it happens:** Blender uses Z-up, code sometimes assumes Y-up. Or forward direction convention mismatch.
**How to avoid:** Every generator must have explicit axis documentation. Quadruped: spine runs along +Y (forward), height along +Z (up), width along X. Test: check that bounding box height dimension (Z extent) is larger than depth (Y extent) for upright objects.
**Warning signs:** Z extent near zero for objects that should have vertical height.

### Pitfall 4: Proportion Bugs (Shield Half-Size, Axe Paper-Thin)
**What goes wrong:** Generated assets have incorrect real-world proportions.
**Why it happens:** Default parameter values are too small, or scale factors are wrong.
**How to avoid:** Define reference dimensions from real weapons. Longsword: 0.9-1.1m total, blade width 5-7cm. Shield: 60-100cm diameter. Battle axe head: 15-25cm wide. Validate dimensions in tests against reference ranges.
**Warning signs:** Dimensions in metadata outside reference range by >20%.

### Pitfall 5: N-Gon Faces in Deformation Zones
**What goes wrong:** Faces with 5+ vertices cause unpredictable deformation under rigging/animation.
**Why it happens:** Cap faces (tip caps, base caps) created as single N-gon fans.
**How to avoid:** All faces in deformation zones must be quads (4 verts) or tris (3 verts). Cap faces should use triangle fan only at non-deforming extremities. Flag N-gons in quality metrics.
**Warning signs:** Face with `len(face) > 4` in joint/deformation zones.

### Pitfall 6: Creature Part Generators Crash (Tuple Error)
**What goes wrong:** `creature_mouth`, `creature_eyelid`, `creature_paw`, `creature_wing`, `creature_serpent` all crash with `'tuple' object has no attribute 'get'`.
**Why it happens:** Server sends parameters as tuples where generators expect dicts (GEN-01 from requirements).
**How to avoid:** Phase 41 (GEN fixes) should fix this before Phase 43. If not done, Phase 43 must fix the parameter dispatch as a prerequisite. Check: does the handler in `__init__.py` pass `params` correctly to the generator function?
**Warning signs:** TypeError on `.get()` call in any creature part generator.

### Pitfall 7: Test Assertion Thresholds Need Updating
**What goes wrong:** After increasing vertex counts, old tests that assert `len(verts) >= 20` still pass but new quality thresholds (e.g., `>= 1500`) are not enforced.
**Why it happens:** Existing tests have low minimum thresholds from the original implementation.
**How to avoid:** Update `min_verts` parameters in test validation calls. Add new tests for AAA-range validation (e.g., `assert 1500 <= len(verts) <= 8000`).
**Warning signs:** All tests pass but assets still look PLACEHOLDER quality.

## Code Examples

### Example 1: Higher-Density Blade Cross-Section (Conceptual)
```python
# Source: analysis of weapon_quality.py _build_cross_section_blade()
# Current: 10 verts per ring, 14 rings = ~140 blade verts
# Target: 14 verts per ring, 40 rings = ~560 blade verts + tip/base detail

# The key change is in the cross-section profile definition:
# Current profile (8 points): simple diamond
#   spine_top -> fuller_top -> bevel_top -> edge -> bevel_bot -> fuller_bot -> spine_bot -> back

# New profile (14 points): detailed lenticular with secondary edges
#   spine_ridge_top -> spine_flat_top -> fuller_inner_top -> fuller_groove_top ->
#   blade_flat_top -> bevel_outer_top -> edge_tip ->
#   bevel_outer_bot -> blade_flat_bot -> fuller_groove_bot -> fuller_inner_bot ->
#   spine_flat_bot -> spine_ridge_bot -> back_center

# This gives proper visual reads at:
# - The spine ridge (visible thickness line down center)
# - The fuller groove (shadow-catching channel)
# - The edge bevel (glint line at cutting edge)
# - The blade flats (main surface area for material display)
```

### Example 2: Articulated Gauntlet Finger Construction
```python
# Source: analysis of armor_meshes.py generate_gauntlet_mesh()
# Current: amorphous blob, 281 verts total
# Target: 5 individual fingers with 4 joint segments each

def _build_finger(
    base_pos: tuple[float, float, float],
    direction: tuple[float, float, float],
    length: float,
    radius: float,
    joints: int = 4,
    segments_per_ring: int = 8,
) -> tuple[list, list]:
    """Build a single articulated finger as tapered cylinder chain.
    
    Each joint has 2 edge loops (above/below bend point) for proper
    deformation. Total per finger: joints * 2 * segments = 64 verts.
    """
    # ... implementation builds cylinder chain with joint bulges
    pass

# 5 fingers x 64 verts = 320 verts for fingers alone
# Plus palm plate (128), cuff (240), knuckle guard (80) = ~768 base
# With plate overlap detail, rivet bumps: target 2000-3500 total
```

### Example 3: Creature Anatomical Landmarks
```python
# Source: analysis of creature_anatomy.py _generate_quadruped_spine()
# Current: smooth elliptical profiles along spine
# Target: anatomical landmarks that break the smooth silhouette

# The profile function needs to add:
def _quadruped_body_profile_v2(props, t):
    """Return (rx, rz) cross-section radii at spine parameter t.
    
    Anatomical landmarks:
    - t=0.15: shoulder blade peak (rx * 1.15 dorsal bump)
    - t=0.25: rib cage maximum (rz * 1.1 lateral)  
    - t=0.45: waist tuck (rx * 0.85, rz * 0.9)
    - t=0.55: hip bone peak (rx * 1.05)
    - t=0.70: rump drop-off
    
    Plus: ventral keel for chest depth
    Plus: dorsal spine ridge (narrow band of increased rx)
    """
    # Base ellipse with anatomical perturbations
    base_rx = props["body_height"] * 0.5
    base_rz = props["body_width"] * 0.5
    
    # Shoulder blade
    if 0.12 < t < 0.18:
        shoulder_t = (t - 0.12) / 0.06
        base_rx *= 1.0 + 0.15 * math.sin(shoulder_t * math.pi)
    
    # Rib cage
    if 0.20 < t < 0.35:
        rib_t = (t - 0.20) / 0.15
        base_rz *= 1.0 + 0.10 * math.sin(rib_t * math.pi)
    
    # Waist tuck
    if 0.40 < t < 0.50:
        waist_t = (t - 0.40) / 0.10
        base_rx *= 1.0 - 0.15 * math.sin(waist_t * math.pi)
        base_rz *= 1.0 - 0.10 * math.sin(waist_t * math.pi)
    
    return base_rx, base_rz
```

### Example 4: Reference Dimensions for Proportion Validation
```python
# Source: real-world weapon measurements + AAA game references
WEAPON_REFERENCE_DIMENSIONS = {
    "longsword": {"total_length": (0.95, 1.15), "blade_width": (0.045, 0.070),
                  "guard_width": (0.18, 0.28), "grip_length": (0.18, 0.25)},
    "greatsword": {"total_length": (1.3, 1.6), "blade_width": (0.06, 0.10),
                   "guard_width": (0.22, 0.35), "grip_length": (0.30, 0.40)},
    "battle_axe": {"total_length": (0.7, 1.0), "head_width": (0.15, 0.25),
                   "head_height": (0.12, 0.20)},
    "round_shield": {"diameter": (0.60, 1.00), "boss_height": (0.05, 0.10),
                     "rim_thickness": (0.01, 0.02)},
    "kite_shield": {"height": (0.80, 1.20), "width": (0.50, 0.70)},
}

# Armor reference (fitted to standardized humanoid)
ARMOR_REFERENCE_DIMENSIONS = {
    "pauldron": {"width": (0.15, 0.22), "height": (0.12, 0.18)},
    "chestplate": {"width": (0.35, 0.45), "height": (0.40, 0.55)},
    "gauntlet": {"length": (0.25, 0.35), "width": (0.10, 0.14)},
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| equipment.py bmesh generators | weapon_quality.py pure Python MeshSpec | v8.0 (2026-04) | Enables headless testing, but kept low vert counts |
| monster_bodies.py assembled primitives | creature_anatomy.py spine-profile extrusion | v8.0 (2026-04) | Better topology but still low density |
| Single file for all weapons | weapon_quality.py + procedural_meshes.py split | v7.0 (2026-03) | 41 weapon types in procedural_meshes + 6 quality in weapon_quality |
| Code-based quality scoring | zai visual verification scoring | v9.0 (2026-04) | Revealed all "AAA" self-scores were wrong |

**Deprecated/outdated:**
- `equipment.py` weapon generators: bmesh-based, low quality, should be replaced by weapon_quality.py calls
- `monster_bodies.py` standalone: largely superseded by creature_anatomy.py but still has brand feature system that needs preserving

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `Tools/mcp-toolkit/pyproject.toml` or `pytest.ini` |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_weapon_quality.py tests/test_creature_anatomy.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GEOM-01 | Weapon verts in 1500-4000 range per type | unit | `pytest tests/test_weapon_quality.py -x -q` | Exists (needs threshold updates) |
| GEOM-01 | Blade cross-section >= 12 verts | unit | `pytest tests/test_weapon_quality.py::TestQualitySword::test_blade_cross_section_not_flat -x` | Exists (needs threshold update) |
| GEOM-01 | Guard extends beyond blade width | unit | `pytest tests/test_weapon_quality.py::TestQualitySword::test_guard_extends_beyond_blade -x` | Exists |
| GEOM-01 | Shield correct dimensions (0.6-1.0m diameter) | unit | `pytest tests/test_weapon_quality.py -k shield -x` | Exists (needs dimension assertion) |
| GEOM-02 | Armor verts in 1500-5000 range | unit | `pytest tests/test_weapon_quality.py -k "pauldron or chestplate or gauntlet" -x` | Exists (needs threshold updates) |
| GEOM-02 | Gauntlet has 5 articulated fingers | unit | New test needed | Wave 0 |
| GEOM-03 | Creature verts in 5000-15000 range | unit | `pytest tests/test_creature_anatomy.py -x` | Exists (import error, needs fix) |
| GEOM-03 | Wolf orientation correct (Z-up) | unit | New test needed | Wave 0 |
| GEOM-03 | Creature part generators don't crash | unit | `pytest tests/test_creature_anatomy.py -k "mouth or eyelid or paw or wing or serpent" -x` | Exists (currently fails) |
| TEST-03 | Visual before/after screenshots | manual | `blender_viewport action=contact_sheet` via MCP | N/A (manual via Blender) |
| TEST-04 | Opus scan CLEAN | manual | N/A (human-driven) | N/A |

### Sampling Rate
- **Per task commit:** `cd Tools/mcp-toolkit && python -m pytest tests/test_weapon_quality.py tests/test_creature_anatomy.py -x -q`
- **Per wave merge:** `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green (19,850+ tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Fix `test_creature_anatomy.py` import error (safe_place_object missing from _shared_utils)
- [ ] Add dimension reference assertions to test_weapon_quality.py (min/max real-world dimensions)
- [ ] Add gauntlet finger articulation test
- [ ] Add wolf/quadruped orientation test (Z extent > 0, bounding box sanity)
- [ ] Update min_verts thresholds in existing tests from current low values to AAA targets

## Open Questions

1. **Phase 41 (GEN fixes) dependency: Are the 5 crashed creature part generators fixed before Phase 43 starts?**
   - What we know: GEN-01 is assigned to Phase 41, which is before Phase 43 in the roadmap
   - What's unclear: Whether Phase 41 will be completed before Phase 43 execution begins
   - Recommendation: Phase 43 planner should check GEN-01 status. If not fixed, include a prerequisite task to fix the tuple parameter dispatch bug in creature part generators.

2. **Phase 40 (MAT wiring) dependency: Will material library be wired before Phase 43?**
   - What we know: MAT-01 (wire material library into ALL generators post-mesh) is Phase 40
   - What's unclear: Whether Phase 43 geometry work should also wire materials or leave that to Phase 40
   - Recommendation: Phase 43 should focus purely on geometry. If materials are not wired by Phase 40, add material assignment as a separate concern, not interleaved with geometry work. However, generators should include proper vertex groups and metadata that the material system needs (e.g., "blade", "guard", "grip", "pommel" groups for per-component material assignment).

3. **Procedural_meshes.py 41 additional weapon types: Do these need the same quality overhaul?**
   - What we know: procedural_meshes.py has 41 weapon types (greatsword, curved_sword, hand_axe, etc.) in addition to the 6 in weapon_quality.py
   - What's unclear: Whether Phase 43 scope includes all 41 or just the 6 + 3 armor + creatures
   - Recommendation: Phase 43 should focus on the 9 QUALITY_GENERATORS (6 weapons + 3 armor) plus creatures. The 41 procedural_meshes weapons are lower priority and could be addressed in a follow-up phase.

4. **armor_meshes.py vs weapon_quality.py: Which file owns armor generators?**
   - What we know: Both files have pauldron and gauntlet generators. weapon_quality.py has the ones dispatched by blender_server.py. armor_meshes.py has a fuller 12-slot system.
   - What's unclear: Which implementation should be the canonical source
   - Recommendation: Keep weapon_quality.py as the canonical source for the 3 armor types currently exposed (pauldron, chestplate, gauntlet). Port improvements back to armor_meshes.py for the other 9 slots in a later phase.

## Environment Availability

Step 2.6: SKIPPED (no external dependencies identified). This phase modifies pure Python generator code and pytest tests. No external tools, services, or runtimes beyond Python 3.13 and pytest are needed.

## Sources

### Primary (HIGH confidence)
- **Codebase analysis**: weapon_quality.py (3090 lines), creature_anatomy.py (3003 lines), armor_meshes.py (2246 lines) -- actual generator code read and vertex counts verified by running generators
- **V9_MASTER_FINDINGS.md**: Sections 7, 8, 17.1-17.3 -- visual verification scorecard with actual vertex counts and zai scores
- **TEXTURING_WEAPONS_ITEMS_RESEARCH.md**: PBR value tables, material tier system, `ASSET_TYPE_BUDGETS: Weapon: 3000-8000 tris`
- **TEXTURING_CHARACTERS_RESEARCH.md**: Creature surface texturing recipes, skin/scales/chitin/membrane PBR values
- **CHARACTER_MESH_QUALITY_TECHNIQUES.md**: Polygon budget reference table (Boss: LOD0 50K, Hero: LOD0 30K, NPC: LOD0 15K)

### Secondary (MEDIUM confidence)
- **Polycount forums** (https://polycount.com/discussion/230710): Modern AAA weapon budgets 1000-40000 tris depending on first/third person. Third-person weapons typically 2000-8000 tris.
- **test_weapon_quality.py / test_creature_anatomy.py**: Existing test infrastructure with validation helpers

### Tertiary (LOW confidence)
- **Elden Ring model analysis**: No specific poly counts available from extracted models. Visual quality bar referenced qualitatively (FromSoftware standard = detailed silhouettes, layered plate armor, anatomical creature musculature).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pure Python generators with no external dependencies, architecture is well-understood
- Architecture: HIGH -- patterns are established, just need density increases within existing structures
- Pitfalls: HIGH -- all pitfalls derived from actual bugs found in V9 audit and verified in codebase
- Vertex targets: MEDIUM -- based on industry references and existing ASSET_TYPE_BUDGETS, but exact counts should be validated visually

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable -- pure Python math generators, no external API changes)
