# Phase 32: Building System -- Research

**Date:** 2026-03-31
**Status:** Complete
**Sources:** Codebase audit (building_grammar, building_quality, modular_building_kit, worldbuilding)

---

## 1. Current State Analysis

### 1.1 Building Grammar (`_building_grammar.py`, 2716 lines)

**What works:**
- `BuildingSpec` dataclass cleanly separates geometry ops from Blender execution
- `evaluate_building_grammar()` produces foundation, walls (4 per floor), floor slabs, roof, windows, doors
- `STYLE_CONFIGS` has 5 well-defined styles: medieval, gothic, rustic, fortress, organic
- `FACADE_STYLE_RULES` has detailed per-style facade parameters (plinth, cornice, pilaster, bay counts)
- `plan_modular_facade()` generates facade enrichment modules (plinth bands, pilasters, cornices, frames)
- Specialized templates: fortress tower kit, castle spec, bridge spec work well with stacked massing

**Critical bugs:**
1. **Detail operations are 0.5m cubes** (line 738-749): gargoyles, buttresses, chimneys, rose windows, spires -- all rendered as identical `{"type": "box", "size": [0.5, 0.5, 0.5]}` placed at random positions
2. **Roof is a flat box** (line 655-698): gabled/pointed roofs are 0.1m-thick boxes with `ridge_height` as metadata-only. No actual slope geometry
3. **Windows/doors are metadata** (line 700-734): openings stored as `{"type": "opening"}` -- the handler in worldbuilding.py does convert these to cutout boxes, but it's a recessed box, not a proper boolean cut
4. **No facade variation**: same number of windows per wall per floor, same door position -- every building of a style is identical

### 1.2 Building Quality (`building_quality.py`, 2775 lines)

**9 AAA generators -- all DISCONNECTED from grammar:**

| Generator | What it produces | Quality |
|---|---|---|
| `generate_stone_wall` | Running bond blocks with mortar gaps, 5 block styles | AAA |
| `generate_timber_frame` | Exposed beams, wattle/daub panels, cross braces | AAA |
| `generate_gothic_window` | Voussoir arches, tracery, mullions, shutters, glass panes | AAA |
| `generate_roof` | Individual tiles/shingles, ridge tiles, fascia, rafters, gable ends | AAA |
| `generate_staircase` | Individual steps, newel posts, handrails (5 styles) | AAA |
| `generate_archway` | Voussoir blocks, imposts, keystone (5 arch styles) | AAA |
| `generate_chimney` | Brick/stone pattern, cap, pot, flashing | GOOD |
| `generate_interior_trim` | Baseboard, crown molding, beams, floor planks, wainscoting | GOOD |
| `generate_battlements` | Crenellations, machicolations, arrow loops | GOOD |

**Key helpers (reusable):**
- `_stone_block_grid()`: running bond layout with variation
- `_arch_curve()`: parametric arch (gothic, roman, horseshoe, Tudor, ogee, lancet)
- `_voussoir_blocks()`: individual wedge-shaped arch stones
- `_molding_profile_extrude()`: profile extrusion along 3D path
- `_shingle_row()`: overlapping roof shingles with stagger

### 1.3 Modular Building Kit (`modular_building_kit.py`, 1551 lines)

**25 piece types across 5 styles = 125 base variants:**

- Walls: solid, window, door, damaged, half, corner_inner, corner_outer, t_junction, end_cap (9)
- Floors: stone, wood, dirt (3)
- Roofs: slope, peak, flat, gutter (4)
- Stairs: straight, spiral, ramp (3)
- Doors: single, double, arched (3)
- Windows: small, large, pointed (3)

**Grid:** 2m horizontal, 3m vertical per floor
**Wall thickness:** style-specific (0.3-0.5m)
**Per-vertex jitter:** style-specific for organic imperfection

**GAP:** Need 25 more piece types to reach 50+ per style. Missing: foundation, column, pillar, balcony, beam, trim, chimney, arch, battlement, dormer, awning, bracket, corbel, gable_end, turret, bay_window, etc.

### 1.4 Worldbuilding Handler (`worldbuilding.py`, 6800+ lines)

- `_spec_to_bmesh()` converts BuildingSpec to Blender geometry
- `_building_ops_to_mesh_spec()` transforms grammar ops to vertex/face data
- `_wall_with_openings()` creates recessed cutout boxes for windows/doors
- `handle_generate_building()` is the main entry point -- calls evaluate_building_grammar, then spec_to_bmesh
- Building grammar result goes through: evaluate_grammar -> ops_to_mesh_spec -> spec_to_bmesh -> create_mesh_object

## 2. Gap Analysis

### 2.1 Grammar -> Quality Wiring (CRITICAL)

The core problem: `evaluate_building_grammar()` produces operations that are consumed by `_building_ops_to_mesh_spec()` which turns them into vertex/face data. All "detail" operations are 0.5m cubes. The building_quality generators produce AAA geometry but as standalone MeshSpec dicts.

**Solution:** Replace the detail generation section (lines 737-749) with calls to building_quality generators that produce proper MeshSpec operations. These can be appended to BuildingSpec.operations and consumed by `_building_ops_to_mesh_spec()`.

Specifically:
- `timber_frame` detail -> use `generate_timber_frame()` from building_quality
- `window_boxes` detail -> use `generate_gothic_window()` with style params
- `chimney` detail -> use `generate_chimney()` from building_quality
- `flying_buttress` detail -> use `generate_archway()` angled as buttress
- `gargoyle` detail -> custom gargoyle geometry (not just a cube)
- `rose_window` detail -> use `generate_gothic_window(style="rose_window")`
- `spire` detail -> pointed cone/pyramid geometry
- `battlement` / `machicolation` / `murder_hole` -> use `generate_battlements()`

### 2.2 Roof Generation

Current roof in grammar is a flat box. Need to wire `generate_roof()` from building_quality (which has gable, hip, gambrel, mansard, shed, conical_tower, flat styles with individual tiles).

For straight skeleton roofs from arbitrary footprints: implement a simplified polyskel algorithm that handles rectangular footprints (hip/gable) and L-shaped/T-shaped footprints.

### 2.3 Facade Variation

Currently every building of a style has identical facade. Need:
- Randomized bay count per floor (within style range)
- Randomized window count per wall (floor-dependent)
- Randomized door position (off-center options)
- Per-building detail selection from style's detail list
- Randomized proportions (floor height +/- 10%, wall thickness +/- 5%)

### 2.4 Modular Kit Expansion

Need 25+ new piece types. Candidates from building_quality generators:
- column_round, column_square (from pillar patterns)
- balcony_simple, balcony_ornate
- foundation_block, foundation_stepped
- beam_horizontal, beam_diagonal, beam_cross
- trim_baseboard, trim_crown, trim_corner
- chimney_stack, chimney_pot
- arch_round, arch_pointed
- battlement_merlon, battlement_crenel
- dormer_gable, dormer_shed
- awning_simple
- bracket_corbel
- gable_end
- turret_round
- bay_window
- pillar_base, pillar_capital

## 3. Implementation Strategy

### Phase 32-01: Grammar Upgrade + Quality Wiring + Roof + Variation

1. **Wire building_quality into grammar details** - Replace 0.5m cube details with real geometry calls
2. **CGA-style facade split** - Recursive floor/bay splitting with fill rules per bay
3. **Roof upgrade** - Wire generate_roof() and add straight skeleton for hip roofs from rectangular footprints
4. **Variation system** - Seed-based randomization of bay counts, window placement, proportions
5. **Expand modular kit to 50+ pieces** - Add foundation, column, balcony, beam, trim, chimney, arch, battlement, dormer, awning, bracket, gable pieces

---

*Research compiled from: codebase audit (2026-03-31), _building_grammar.py, building_quality.py, modular_building_kit.py, worldbuilding.py*
