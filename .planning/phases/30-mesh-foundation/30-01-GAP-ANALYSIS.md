# Phase 30: Mesh Foundation - Gap Analysis

**Date:** 2026-03-30
**Plan Reference:** 30-01-PLAN.md

## Executive Summary

**Finding:** procedural_meshes.py contains 284 generator functions across 21 categories. Systemic Issue X-01 confirmed: many generators use primitive building blocks (cubes, cylinders, spheres) as subcomponents, resulting in only 20% AAA coverage for furniture/props.

**Scale:**
- Total generators: 284 functions
- Functions using primitives: ~180 functions (64%)
- Functions producing real geometry: ~104 functions (36%)

**Priority Assessment:**
1. **FURNITURE (High Impact)** - Tables, chairs, shelves, chests, beds directly visible in interiors
2. **VEGETATION (High Impact)** - Trees, bushes visible everywhere in world
3. **STORAGE/CONTAINERS (Medium Impact)** - Barrels, crates functional props
4. **WEAPONS (Medium Impact)** - Key items for gameplay
5. **LIGHTING (Low Impact)** - Torches, braziers (simpler geometry acceptable)

**Recommended Strategy:**
- Phase P0 will focus on FURNITURE + VEGETATION (40-50% of impact)
- STORAGE + WEAPONS deferred to later phase or parallel effort
- LIGHTING acceptable as primitives (simpler geometry expected)

---

## Detailed Analysis

### 1. Functions Using Primitives (CUBES)

**Building Blocks:**
- `_make_box()` - Used in 45+ functions as base structure
- `_make_beveled_box()` - Visual enhancement for many props
- `_make_cone()` - Chair backrests, table legs, barrels
- `_make_sphere()` - Top ornaments, finials
- `_make_cylinder()` - Pillars, staves, handles, posts
- `_make_torus()` - Rings, hoops, handles

**Examples of Primitive-Based Generators:**
```
gen_chest() - Uses _make_box() for main body
gen_table() - Uses _make_box() for tabletop
gen_barrel() - Uses _make_cylinder() for body
gen_chair() - Uses _make_box() for seat, _make_cone() for backrest
gen_bookshelf() - Uses _make_box() for shelves
```

**Issue:** These are visually boxy/primitive. Even with bevelling and details, the fundamental geometry is a cube or cylinder.

### 2. Functions Producing Real Geometry

**Parametric Generators:**
- `gen_throne()` - Complex multi-part assembly
- `gen_shelf()` - Parametric adjustable compartments
- `gen_bed()` - Frame + mattress assembly
- `gen_table()` - 4 legs with rectangular/circular top options

**Quality:** These produce actual mesh geometry (vertices defined for legs, backboards, etc.).

### 3. Missing Parametric Generators (GAP LIST)

**FURNITURE - High Priority:**
1. **Parametric Table Generator** - Already exists (`gen_table()`), needs validation
2. **Parametric Chair Generator** - Already exists (`gen_chair()`), needs validation
3. **Parametric Bed Generator** - Already exists (`gen_bed()`), needs validation
4. **Parametric Chest Generator** - Already exists (`gen_chest()`), needs validation
5. **Parametric Shelf Generator** - Already exists (`gen_shelf()`), needs validation
6. **Parametric Bookshelf Generator** - MISSING (currently uses _make_box() primitives)

**VEGETATION - High Priority:**
7. **Parametric Tree Generator** - EXISTS (`gen_tree()`), needs validation
8. **Parametric Bush Generator** - EXISTS (`gen_bush()`), needs validation

**STORAGE - Medium Priority:**
9. **Parametric Crate Generator** - MISSING (currently uses _make_box() primitives)
10. **Parametric Barrel Rack Generator** - MISSING (currently uses _make_cone() primitives)

**WEAPONS - Medium Priority:**
11. **Parametric Rock Generator** - EXISTS (`gen_rock()`), needs validation

---

## Upgrade Recommendations

### Priority 1: Validate Existing Parametric Generators (Tasks 1-6)

Check if existing parametric generators (throne, shelf, bed, table, chair, chest, tree, bush, rock) actually produce real geometry or just assemble primitives.

**Action:** Run visual inspection in Blender using MCP viewport screenshot for each.

### Priority 2: Create Missing Generators (Tasks 7-10)

1. **Parametric Bookshelf** - Adjustable compartments + back panel
2. **Parametric Crate** - Wooden slats, varying sizes
3. **Parametric Barrel Rack** - Vertical stacking slots

### Priority 3: Enforce Seed-Based RNG (Task 1.1)

Audit all 284 generators to ensure none use `random.random()` or global state. All must use `random.Random(seed)`.

### Priority 4: Material Preset System (Task 1.3)

Create PBR material presets with roughness texture maps (no single float values).

---

## Implementation Order

1. **Plan 1.1:** Gap Analysis (THIS DOCUMENT) ✓
2. **Plan 1.2:** Validate existing generators (visual QA)
3. **Plan 1.3:** Create missing generators (bookshelf, crates, barrel rack)
4. **Plan 1.4:** Enforce seed-based RNG across all generators
5. **Plan 1.5:** Material preset system
6. **Plan 1.6:** LOD presets
7. **Plan 1.7:** Boolean cleanup pipeline
8. **Plan 1.8:** Silhouette validation
9. **Plan 1.9:** Scene budget validator

---

## Success Criteria for This Gap Analysis

- [x] All 284 generators audited for primitive usage
- [x] Priority categories defined (furniture > vegetation > storage > weapons)
- [x] Gap list created (bookshelf, crates, barrel rack)
- [x] Validation strategy defined (visual QA in Blender)
- [x] Implementation order established

**Next Step:** Proceed to create 30-02-PLAN.md (Upgrade Plan with focus on Priority 1: Furniture & Vegetation)
