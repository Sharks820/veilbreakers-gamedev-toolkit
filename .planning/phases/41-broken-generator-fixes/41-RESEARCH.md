# Phase 41: Broken Generator Fixes - Research

**Researched:** 2026-04-04
**Domain:** Blender Python procedural mesh generators (creature anatomy, vegetation, worldbuilding, weapon/armor proportions)
**Confidence:** HIGH

## Summary

Phase 41 addresses 11 distinct broken generators and proportion/orientation bugs across 7 handler files. Through direct code inspection, the root causes have been precisely identified for every bug. The fixes range from trivial one-line parameter corrections (boss arena `cap_fill` -> `cap_ends`) to structural changes (creature generators return tuples instead of MeshSpec dicts) to deeper geometric axis-orientation corrections (wolf uses Z-forward instead of Y-forward, door uses Y-up instead of Z-up).

The most impactful fix by volume is GEN-01 (5 creature part generators), which all share the same root cause: functions return `(verts, faces, groups)` tuples but `_build_quality_object()` expects a MeshSpec dict. The fix is to wrap each function's return in a proper MeshSpec dict, OR add a conversion layer in `_build_quality_object` to detect and convert tuples. The vegetation fixes (GEN-02/03) require wiring `mesh_from_spec` into the handler for trees, and providing actual branch_tips data for leaf cards. The town generator crash (GEN-05) is caused by unbounded building generation on a 200x200 grid -- the fix requires capping building count and reducing grid size.

**Primary recommendation:** Fix all 7 GEN requirements by modifying handler code in `__init__.py`, `creature_anatomy.py`, `vegetation_lsystem.py`, `worldbuilding.py`, `worldbuilding_layout.py`, `weapon_quality.py`, and `building_quality.py`. Each fix has a precisely identified root cause and known solution.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GEN-01 | Fix 5 crashed creature part generators (tuple error) | Root cause: `generate_mouth_interior`, `generate_eyelid_topology`, `generate_paw`, `generate_wing`, `generate_serpent_body` return `(verts, faces, groups)` tuples but `_build_quality_object()` at line 626 calls `.get()` expecting a dict. Fix: wrap returns in MeshSpec dicts or add tuple-to-MeshSpec adapter. |
| GEN-02 | Fix vegetation_tree (returns raw vertex data) | Root cause: `__init__.py:1087` handler calls `generate_lsystem_tree(params)` and returns raw dict -- never calls `mesh_from_spec()` or `_build_quality_object()` to create a Blender object. Fix: pipe through `_build_quality_object()`. |
| GEN-03 | Fix vegetation_leaf_cards (generates 0) | Root cause: `__init__.py:1089` passes `branch_tips=params.get("branch_tips", [])` -- empty list default means 0 tips, 0 cards. Fix: when called standalone, generate default branch tip positions; when called after tree, use tree's `tip_positions`. |
| GEN-04 | Fix boss arena generator (cap_fill API break) | Root cause: `worldbuilding.py:6983` uses `bmesh.ops.create_circle(bm, cap_fill=True, ...)` -- `cap_fill` was never a valid bmesh parameter. Correct parameter is `cap_ends=True`. Same bug at lines 3200 and 3544. |
| GEN-05 | Fix town generator (crashes Blender) | Root cause: `worldbuilding_layout.py` calls `handle_generate_building()` for every building plot on a 200x200 grid. Each building is 54K+ verts. Unbounded plot count * heavy building generation = OOM/crash. Fix: cap grid size, limit building count, add progress guards. |
| GEN-06 | Fix orientation bugs (wolf upside-down, door flat, shield horizontal) | Root cause: (1) Wolf: `creature_anatomy.py:587` spine runs along Z-axis, height on Y -- should be Y-forward, Z-up. (2) Door: `riggable_objects.py:664-674` uses Y for height -- should use Z. (3) Shield: generated in XY plane but needs -90deg X rotation; `_build_quality_object` only rotates items with weapon vertex groups. |
| GEN-07 | Fix proportion bugs (shield half-size, axe thin, mace undersized, merlons undersized) | Root cause: (1) Shield: kite preset width=0.25m, height=0.50m (real: ~0.55-0.60m wide, 0.90-1.0m tall). (2) Axe head_thickness=0.025m (should be 0.04-0.05m). (3) Mace head_radius=0.04m (should be 0.06-0.08m). (4) Merlons: building_quality.py:2785-2786 has 0.6m wide / 0.8m tall (historical: 1.2-1.5m wide / 0.9-2.1m tall). Worldbuilding.py tower merlons even smaller at 0.22m min width. |
| TEST-04 | Opus verification scan after phase | Verification scans run until clean after all fixes applied. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Blender Python (bpy) | 5.0+ | All mesh generation and scene manipulation | Runtime environment |
| bmesh | 5.0+ | Low-level mesh operations (create_circle, etc.) | Blender standard for procedural geometry |
| mathutils | 5.0+ | Vector/matrix math | Blender standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.0+ | Test runner | All test execution |
| pytest-asyncio | 0.24+ | Async test support | MCP server tests |

**No new dependencies needed.** All fixes are modifications to existing handler code.

## Architecture Patterns

### Handler Architecture (existing, must follow)
```
Tools/mcp-toolkit/
  blender_addon/
    handlers/
      __init__.py              # COMMAND_HANDLERS dict, _build_quality_object()
      creature_anatomy.py      # GEN-01, GEN-06 (wolf)
      vegetation_lsystem.py    # GEN-02, GEN-03
      worldbuilding.py         # GEN-04 (boss arena cap_fill)
      worldbuilding_layout.py  # GEN-05 (town crash)
      riggable_objects.py      # GEN-06 (door orientation)
      weapon_quality.py        # GEN-06 (shield), GEN-07 (proportions)
      building_quality.py      # GEN-07 (merlon sizing)
      _mesh_bridge.py          # mesh_from_spec(), MeshSpec type
  tests/
    test_creature_anatomy.py   # Existing tests for creature generators
    test_vegetation_lsystem.py # Existing tests for vegetation
    test_worldbuilding_handlers.py  # Existing worldbuilding tests
    test_riggable_objects.py   # Existing riggable tests
```

### Pattern 1: MeshSpec Dict Format
**What:** All generators that feed into `_build_quality_object()` must return a MeshSpec dict.
**When to use:** Every mesh generator that creates Blender objects via the handler system.
**Example:**
```python
# Source: Tools/mcp-toolkit/blender_addon/handlers/_mesh_bridge.py:116
MeshSpec = dict[str, Any]
# Required keys: "vertices", "faces"
# Optional keys: "uvs", "vertex_groups", "metadata", "empties",
#                "sharp_edges", "crease_edges"
```

### Pattern 2: _build_quality_object Flow
**What:** Takes a MeshSpec dict, calls mesh_from_spec(), applies smooth shading, creates empties and vertex groups.
**When to use:** All quality generator handlers in COMMAND_HANDLERS.
**Key code path:**
```python
# __init__.py:626 -- the line that crashes on tuples
category = spec.get("metadata", {}).get("category", "")
is_weapon = category == "weapon" or any(
    k in spec.get("vertex_groups", {}) for k in ("blade", "shaft", "limb")
)
rot = (-math.pi / 2, 0.0, 0.0) if is_weapon else (0.0, 0.0, 0.0)
obj = mesh_from_spec(spec, location=loc, rotation=rot)
```

### Pattern 3: Blender Coordinate Convention
**What:** Blender uses right-handed Z-up: X=right, Y=forward (into screen), Z=up.
**When to use:** ALL geometry generation.
**Critical rule:** Height/vertical = Z axis. Forward/body-length = Y axis. Width/horizontal = X axis.

### Anti-Patterns to Avoid
- **Using Y for vertical:** Door and quadruped generators use Y for height. In Blender, Z is up. This creates lying-flat geometry.
- **Using Z for forward:** Quadruped spine runs along Z (body length). Should run along Y.
- **Returning raw tuples from generators wired to _build_quality_object:** Must return MeshSpec dicts.
- **Unbounded generation loops:** Town generator creates buildings for every plot without limits.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tuple-to-MeshSpec conversion | Ad-hoc dict wrapping in each caller | Single `_tuple_to_meshspec()` utility | 5 generators need same conversion; DRY |
| Circle fill in bmesh | Custom face creation | `bmesh.ops.create_circle(bm, cap_ends=True, ...)` | Correct API parameter |
| Mesh object creation | Direct bpy.data calls | `mesh_from_spec()` / `_build_quality_object()` | Handles UVs, normals, groups, shading |

## Common Pitfalls

### Pitfall 1: Tuple Return Mismatch
**What goes wrong:** Generator returns `(verts, faces, groups)` tuple, handler passes to `_build_quality_object()` which calls `.get()` on it.
**Why it happens:** Creature generators were written as pure-logic functions returning raw data, but the handler wiring expects MeshSpec dicts.
**How to avoid:** Either modify generators to return MeshSpec dicts, OR create a `_creature_tuple_to_meshspec()` adapter in `__init__.py`.
**Warning signs:** `'tuple' object has no attribute 'get'` error.

### Pitfall 2: Axis Convention Violations
**What goes wrong:** Objects appear rotated 90 degrees, lying flat, or upside-down.
**Why it happens:** Blender is Z-up, but many generators use Y for vertical (common in math/OpenGL convention).
**How to avoid:** All geometry: height=Z, forward=Y, right=X. Verify by checking if newly placed objects sit correctly on the XY ground plane.
**Warning signs:** Objects need manual rotation after generation.

### Pitfall 3: cap_fill vs cap_ends
**What goes wrong:** `TypeError: bmesh.ops.create_circle() got an unexpected keyword argument 'cap_fill'`.
**Why it happens:** The parameter name is `cap_ends`, never `cap_fill`. Code has wrong parameter name.
**How to avoid:** Use `cap_ends=True` for filled circles, `cap_ends=False` for ring-only.
**Warning signs:** Any `cap_fill` usage in bmesh calls.

### Pitfall 4: Empty branch_tips Default
**What goes wrong:** Leaf card generator produces 0 vertices, 0 cards.
**Why it happens:** `branch_tips=params.get("branch_tips", [])` defaults to empty list. No tips = no leaves.
**How to avoid:** When calling standalone (no tree context), generate synthetic branch tips. When calling after tree generation, pipe tree's `tip_positions` and `tip_directions` into leaf card generator.
**Warning signs:** Leaf card result has 0 vertices.

### Pitfall 5: Town Generator OOM
**What goes wrong:** Blender crashes or freezes during town generation.
**Why it happens:** 200x200 Voronoi grid creates many building plots, each invoking full `handle_generate_building()` (54K+ verts). No count limit.
**How to avoid:** (1) Reduce default grid from 200x200 to 60x60 or smaller. (2) Cap max buildings (e.g., 15-20). (3) Add early exit if structure_count exceeds limit. (4) Use simpler building variants for background buildings.
**Warning signs:** Building generation taking > 30 seconds, Blender memory climbing rapidly.

### Pitfall 6: Orientation Check in _build_quality_object is Too Narrow
**What goes wrong:** Shield and door don't get the rotation they need because they lack weapon vertex groups.
**Why it happens:** `_build_quality_object` only checks for `"blade"`, `"shaft"`, `"limb"` vertex groups to decide rotation. Shields have `"boss"`, `"grip_bar"`, `"arm_strap"`. Doors have `"hinge"`, `"panel"`, `"frame"`.
**How to avoid:** Either: (a) expand the rotation detection to cover more categories, (b) add a `metadata.category` field to each generator's output and use that for orientation logic, or (c) fix the geometry coordinates directly.
**Warning signs:** Shield rendered horizontal, door rendered flat on ground.

## Code Examples

### Fix 1: Creature Tuple-to-MeshSpec Adapter
```python
# Add to __init__.py near _build_quality_object
def _creature_tuple_to_meshspec(
    result: tuple,
    name: str,
    category: str = "creature",
) -> MeshSpec:
    """Convert creature generator (verts, faces, groups[, bones]) tuple to MeshSpec."""
    verts = result[0]
    faces = result[1]
    groups = result[2] if len(result) > 2 else {}
    bones = result[3] if len(result) > 3 else {}
    return {
        "vertices": verts,
        "faces": faces,
        "vertex_groups": groups if isinstance(groups, dict) else {},
        "metadata": {
            "category": category,
            "vertex_count": len(verts),
            "poly_count": len(faces),
        },
    }
```

### Fix 2: Boss Arena cap_fill -> cap_ends
```python
# worldbuilding.py:6983 -- BEFORE
bmesh.ops.create_circle(bm, cap_fill=True, segments=32, radius=diameter / 2)
# AFTER
bmesh.ops.create_circle(bm, cap_ends=True, segments=32, radius=diameter / 2)

# Same fix at lines 3200 and 3544
```

### Fix 3: Vegetation Tree -- Wire mesh_from_spec
```python
# __init__.py:1087 -- BEFORE
"vegetation_lsystem_tree": lambda params: generate_lsystem_tree(params),
# AFTER
"vegetation_lsystem_tree": lambda params: _build_quality_object(
    generate_lsystem_tree(params)
),
```

### Fix 4: Leaf Cards -- Default Branch Tips
```python
# __init__.py:1088-1093 -- BEFORE
"vegetation_leaf_cards": lambda params: generate_leaf_cards(
    branch_tips=params.get("branch_tips", []),
    ...
),
# AFTER -- generate synthetic tips if none provided
"vegetation_leaf_cards": lambda params: generate_leaf_cards(
    branch_tips=params.get("branch_tips") or _default_branch_tips(
        count=params.get("tip_count", 20),
        spread=params.get("spread", 3.0),
        height=params.get("height", 5.0),
        seed=params.get("seed", 42),
    ),
    ...
),
```

### Fix 5: Orientation Constants for _build_quality_object
```python
# __init__.py -- expand orientation detection
category = spec.get("metadata", {}).get("category", "")
vgroups = spec.get("vertex_groups", {})

is_weapon = category == "weapon" or any(
    k in vgroups for k in ("blade", "shaft", "limb")
)
is_shield = category == "armor" or "boss" in vgroups or "grip_bar" in vgroups
is_door = "hinge" in vgroups or "panel" in vgroups

# Weapons and shields: rotate from Y-forward to Z-up display
if is_weapon or is_shield:
    rot = (-math.pi / 2, 0.0, 0.0)
# Doors: already vertical if coordinates fixed
else:
    rot = (0.0, 0.0, 0.0)
```

### Fix 6: Shield Proportion Corrections
```python
# weapon_quality.py:2169-2175 -- BEFORE
presets = {
    "kite": {"width": 0.25 * size, "height": 0.50 * size, ...},
    ...
}
# AFTER (historically accurate dimensions)
presets = {
    "round":  {"width": 0.55 * size, "height": 0.55 * size, "convex": 0.06, "rim_thick": 0.018},
    "kite":   {"width": 0.55 * size, "height": 0.95 * size, "convex": 0.05, "rim_thick": 0.015},
    "heater": {"width": 0.50 * size, "height": 0.70 * size, "convex": 0.05, "rim_thick": 0.015},
    "buckler":{"width": 0.30 * size, "height": 0.30 * size, "convex": 0.06, "rim_thick": 0.020},
    "tower":  {"width": 0.60 * size, "height": 1.20 * size, "convex": 0.04, "rim_thick": 0.018},
    "pavise": {"width": 0.65 * size, "height": 1.30 * size, "convex": 0.05, "rim_thick": 0.018},
}
```

### Fix 7: Merlon Proportion Corrections
```python
# building_quality.py:2785-2786 -- BEFORE
merlon_w = 0.6
merlon_h = 0.8
# AFTER (historically accurate)
merlon_w = 1.2   # 1.2-1.5m standard
merlon_h = 1.2   # 0.9-2.1m range, 1.2m is common

# worldbuilding.py:1620-1622 -- tower merlons also undersized
# BEFORE
merlon_w = max(0.22, radius * 0.18)
merlon_h = max(0.55, crown_height * 0.55)
# AFTER
merlon_w = max(0.60, radius * 0.25)
merlon_h = max(0.90, crown_height * 0.65)
```

## Bug Root Cause Summary

| Bug ID | File:Line | Root Cause | Fix Type | Complexity |
|--------|-----------|------------|----------|------------|
| GEN-01 | creature_anatomy.py:1076,1409,1590,1825,2023 | Returns tuple, not MeshSpec dict | Adapter function | LOW |
| GEN-01 | __init__.py:1237-1270 | Passes tuple to _build_quality_object | Wrap in adapter | LOW |
| GEN-02 | __init__.py:1087 | Never calls mesh_from_spec/build_quality_object | Wire through builder | LOW |
| GEN-03 | __init__.py:1089 | branch_tips defaults to [] | Generate default tips | MEDIUM |
| GEN-04 | worldbuilding.py:3200,3544,6983 | cap_fill is wrong param name | Change to cap_ends | LOW |
| GEN-05 | worldbuilding_layout.py:451-501 | Unbounded building generation on 200x200 grid | Cap grid+count | MEDIUM |
| GEN-06a | creature_anatomy.py:587 | Spine uses Z-forward (should be Y) | Swap Y/Z in spine | MEDIUM |
| GEN-06b | riggable_objects.py:664-674 | Door uses Y for height (should be Z) | Swap Y/Z in door | MEDIUM |
| GEN-06c | __init__.py:626-630 | Shield not detected for rotation | Expand category check | LOW |
| GEN-07a | weapon_quality.py:2170 | Shield presets ~50% of real size | Double dimensions | LOW |
| GEN-07b | weapon_quality.py:1473 | Axe head_thickness=0.025m | Increase to 0.04m | LOW |
| GEN-07c | weapon_quality.py:1746 | Mace head_radius=0.04m | Increase to 0.07m | LOW |
| GEN-07d | building_quality.py:2785-2786 | Merlon 0.6m wide, 0.8m tall | Increase to 1.2m/1.2m | LOW |
| GEN-07e | worldbuilding.py:1620-1622 | Tower merlon min 0.22m wide | Increase mins | LOW |

## Exact File Locations

### GEN-01: Creature Part Generators (5 crashes)
- **Handler wiring:** `__init__.py:1237-1270` (5 lambda entries in COMMAND_HANDLERS)
- **Generator functions:**
  - `creature_anatomy.py:934` - `generate_mouth_interior()` returns `(verts, faces, groups)` at line 1076
  - `creature_anatomy.py:1309` - `generate_eyelid_topology()` returns `(verts, faces, groups)` at line 1409
  - `creature_anatomy.py:1417` - `generate_paw()` returns `(verts, faces, groups)` at line 1590
  - `creature_anatomy.py:1661` - `generate_wing()` returns `(verts, faces, groups, bones)` at line 1825
  - `creature_anatomy.py:1906` - `generate_serpent_body()` returns `(verts, faces, groups, bones)` at line 2023
- **Crash point:** `__init__.py:626` - `spec.get("metadata", {})` fails because `spec` is a tuple

### GEN-02: Vegetation Tree
- **Handler:** `__init__.py:1087` - `"vegetation_lsystem_tree": lambda params: generate_lsystem_tree(params)`
- **Generator:** `vegetation_lsystem.py:610` - returns MeshSpec dict correctly
- **Problem:** Handler returns raw dict to TCP caller, never creates Blender object

### GEN-03: Vegetation Leaf Cards
- **Handler:** `__init__.py:1088-1093`
- **Generator:** `vegetation_lsystem.py:751`
- **Problem:** `branch_tips=params.get("branch_tips", [])` -- empty list by default

### GEN-04: Boss Arena
- **Crash sites:** `worldbuilding.py:3200`, `worldbuilding.py:3544`, `worldbuilding.py:6983`
- **Error:** `cap_fill=True` is not a valid keyword for `bmesh.ops.create_circle`
- **Fix:** Replace with `cap_ends=True`

### GEN-05: Town Generator
- **Handler:** `worldbuilding_layout.py:321` - `handle_generate_town()`
- **Layout generation:** `_dungeon_gen.py:693` - `generate_town_layout()` (200x200 Voronoi grid)
- **Building loop:** `worldbuilding_layout.py:451-501` - iterates all plots, calls `handle_generate_building()`
- **Settlement overlay:** `worldbuilding_layout.py:524-542` - also heavy, can fail

### GEN-06: Orientation Bugs
- **Wolf:** `creature_anatomy.py:560-637` - `_generate_quadruped_spine()` uses Z for body-length (line 587: `z = t * total_length`) and Y for height (line 593: `y = body_height + ...`)
- **Door:** `riggable_objects.py:664-674` - `_make_box(..., height / 2, ...)` uses Y for vertical
- **Shield:** `__init__.py:627-630` - orientation check only matches weapon vertex groups

### GEN-07: Proportion Bugs
- **Shield:** `weapon_quality.py:2169-2175` - all preset dimensions ~50% of real
- **Axe:** `weapon_quality.py:1473` - `head_thickness: float = 0.025`
- **Mace:** `weapon_quality.py:1746` - `head_radius: float = 0.04`
- **Merlons (battlements):** `building_quality.py:2785` - `merlon_w = 0.6`, `merlon_h = 0.8`
- **Merlons (towers):** `worldbuilding.py:1620` - `merlon_w = max(0.22, radius * 0.18)`
- **Merlons (tower at building_quality):** `building_quality.py:1555-1557` - `merlon_w = max(0.18, ...)`, `merlon_h = max(0.32, ...)`

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | `Tools/mcp-toolkit/pyproject.toml` (line 34) |
| Quick run command | `cd Tools/mcp-toolkit && python -m pytest tests/test_creature_anatomy.py tests/test_vegetation_lsystem.py tests/test_worldbuilding_handlers.py tests/test_riggable_objects.py -x -q` |
| Full suite command | `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GEN-01 | Creature parts return MeshSpec, not tuple | unit | `pytest tests/test_creature_anatomy.py -x -q -k "mouth or eyelid or paw or wing or serpent"` | Exists but tests tuple unpacking (must update) |
| GEN-02 | vegetation_tree creates Blender object | unit | `pytest tests/test_vegetation_lsystem.py -x -q -k "lsystem_tree"` | Exists (tests raw output, needs Blender object check) |
| GEN-03 | vegetation_leaf_cards generates >0 cards standalone | unit | `pytest tests/test_vegetation_lsystem.py -x -q -k "leaf_cards"` | Exists (needs standalone-without-tips test) |
| GEN-04 | Boss arena generates without crash | unit | `pytest tests/test_worldbuilding_handlers.py -x -q -k "boss_arena"` | Needs new test |
| GEN-05 | Town generates without crash at building_count=3-10 | unit | `pytest tests/test_worldbuilding_handlers.py -x -q -k "town"` | Needs new test or update |
| GEN-06 | Wolf Z-extent > X-extent (standing), door Z-extent > Y-extent, shield Z-extent > X-extent | unit | `pytest tests/test_creature_anatomy.py tests/test_riggable_objects.py -x -q -k "orientation"` | Needs new tests |
| GEN-07 | Shield kite height > 0.8m, mace radius > 0.05m, merlon width > 1.0m | unit | `pytest tests/test_creature_anatomy.py tests/test_riggable_objects.py -x -q -k "proportion"` | Needs new tests |
| TEST-04 | Full suite passes | integration | `pytest tests/ -x -q` | Existing (19,850+ tests baseline) |

### Sampling Rate
- **Per task commit:** Quick run of affected test files
- **Per wave merge:** Full suite `cd Tools/mcp-toolkit && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before verification

### Wave 0 Gaps
- [ ] New test for GEN-04: boss arena cap_ends fix verification
- [ ] New test for GEN-05: town generator stability at small counts
- [ ] New test for GEN-06: orientation assertions (bounding box axis checks)
- [ ] New test for GEN-07: proportion assertions (dimension minimums)
- [ ] Update existing creature tests to verify MeshSpec dict return (not tuple unpacking)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `cap_fill=True` in create_circle | `cap_ends=True` | Never correct -- cap_fill was never a valid bmesh parameter | Fixes boss arena crash |
| Creature generators return raw tuples | Must return MeshSpec dicts for handler system | v8.0 introduced _build_quality_object | 5 generators incompatible |
| Y-up convention in some generators | Z-up everywhere (Blender standard) | Recurring systemic bug | Wolf, door, shield orientation |

## Open Questions

1. **Town generator building complexity**
   - What we know: Each building is 54K+ verts. Unbounded plot count causes crash.
   - What's unclear: Exactly how many plots a 200x200 grid generates (depends on district layout). Whether reducing grid to 60x60 produces acceptable visual density.
   - Recommendation: Cap at 15-20 buildings max AND reduce grid to ~80x80. Add early-exit guard.

2. **Quadruped spine axis swap scope**
   - What we know: Spine runs along Z, height along Y. Need to swap.
   - What's unclear: Whether other functions in creature_anatomy.py that call the spine depend on the current axis convention (legs, head, tail attachment points all reference spine coordinates).
   - Recommendation: Audit all callers of `_generate_quadruped_spine()` before swapping. The bone positions, breathing group, and leg attachment all use spine coordinates.

3. **Door coordinate swap impact**
   - What we know: Door uses Y for height. Need Z for height.
   - What's unclear: Whether iron straps, hinges, and other door sub-components also use the wrong axis.
   - Recommendation: Full audit of door sub-functions (`_plank_row`, `_iron_strap`, `_rivet`, etc.) since they all share the same Y-as-height convention and must all be swapped together.

## Project Constraints (from CLAUDE.md)

- **Always verify visually** after Blender mutations (use `blender_viewport action=contact_sheet`)
- **Pipeline order**: repair -> UV -> texture -> rig -> animate -> export
- **Batch when possible**: Use batch_process and batch_export
- **Use seeds** for reproducible generation
- **Blender Z-up**: Z is up in Blender, Y-up in Unity. Conversion at EXPORT time ONLY.
- **Material creation**: When creating ANY Blender material, ALWAYS set Base Color
- **Bug scan protocol**: Run follow-up scan rounds until CLEAN

## Sources

### Primary (HIGH confidence)
- Direct code inspection of all affected handler files (creature_anatomy.py, vegetation_lsystem.py, worldbuilding.py, worldbuilding_layout.py, riggable_objects.py, weapon_quality.py, building_quality.py, __init__.py, _mesh_bridge.py)
- V9_MASTER_FINDINGS.md sections 8, 17.3, 17.6, 17.7, 17.10, 19.4
- [Blender BMesh API documentation](https://docs.blender.org/api/current/bmesh.ops.html) - confirmed `cap_ends` parameter name

### Secondary (MEDIUM confidence)
- Historical medieval weapon/armor dimensions (shield, merlon proportions) - based on common reference values

## Metadata

**Confidence breakdown:**
- Bug root causes: HIGH - every bug traced to exact file:line with verified code inspection
- Fix approaches: HIGH - standard patterns already used elsewhere in codebase (MeshSpec, _build_quality_object)
- Proportion values: MEDIUM - based on general historical reference, may need visual tuning
- Town crash fix: MEDIUM - grid size/count caps need empirical testing for visual quality

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (stable -- code changes only if phases 39-40 land first)
