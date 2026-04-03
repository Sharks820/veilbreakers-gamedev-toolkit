# Deep Bug Scan: blender_quality Tool (32 AAA Generators)

**Date:** 2026-04-02
**Scope:** blender_server.py (blender_quality dispatch, lines 5057-5331), handlers/__init__.py (_build_quality_object + COMMAND_HANDLERS dispatch, lines 609-1390), _mesh_bridge.py (mesh_from_spec + CATEGORY_MATERIAL_MAP), weapon_quality.py, creature_anatomy.py, riggable_objects.py, clothing_system.py, vegetation_lsystem.py, texture_quality.py
**Method:** Full read of dispatch logic, cross-reference of function signatures vs call sites, return type analysis, parameter forwarding audit
**Scan #:** 20 (previous 19 scans found ~280 bugs)

---

## CRITICAL BUGS (Will cause crashes)

### BUG-01: 5 creature generators return tuples, _build_quality_object expects dict -- AttributeError crash
**Files:** `creature_anatomy.py` (generators), `handlers/__init__.py` (dispatch, lines 1229-1255)
**Severity:** CRITICAL (crash on every call to these 5 actions)
**Affected actions:** `creature_mouth`, `creature_eyelid`, `creature_paw`, `creature_wing`, `creature_serpent`

**Description:** Five creature anatomy generators return tuples, not MeshSpec dicts:

| Generator | Return type | Line |
|-----------|-------------|------|
| `generate_mouth_interior()` | `tuple[VertList, FaceList, dict]` | creature_anatomy.py:1076 |
| `generate_eyelid_topology()` | `tuple[VertList, FaceList, dict]` | creature_anatomy.py:1409 |
| `generate_paw()` | `tuple[VertList, FaceList, dict]` | creature_anatomy.py:1446 |
| `generate_wing()` | `tuple[VertList, FaceList, dict, dict]` | creature_anatomy.py:1825 |
| `generate_serpent_body()` | `tuple[VertList, FaceList, dict, dict]` | creature_anatomy.py:2023 |

The dispatch in `__init__.py` passes these tuples directly to `_build_quality_object(spec: dict)`:
```python
# Line 1229 -- will crash
"creature_mouth_interior": lambda params: _build_quality_object(generate_mouth_interior(
    mouth_width=params.get("mouth_width", 0.1), ...
), position=tuple(params.get("position", (0.0, 0.0, 0.0)))),
```

`_build_quality_object` immediately calls `spec.get("metadata", {})` (line 622), which raises `AttributeError: 'tuple' object has no attribute 'get'`.

The other two creature generators (`generate_quadruped`, `generate_fantasy_creature`) return dicts with `"vertices"` and `"faces"` keys, so they work -- but see BUG-02.

**Fix:** Add a wrapper function that converts `(verts, faces, groups[, bones])` tuples into proper MeshSpec dicts before passing to `_build_quality_object`. Example:
```python
def _creature_tuple_to_spec(result, name="creature_part"):
    if isinstance(result, dict):
        return result
    verts, faces = result[0], result[1]
    groups = result[2] if len(result) > 2 else {}
    bones = result[3] if len(result) > 3 else {}
    return {
        "vertices": verts, "faces": faces,
        "vertex_groups": groups if isinstance(groups, dict) else {},
        "metadata": {"name": name, "category": "creature",
                     "vertex_count": len(verts), "poly_count": len(faces)},
    }
```

### BUG-02: vegetation_tree and vegetation_leaf_cards never create Blender objects
**Files:** `blender_server.py` (lines 5301-5310), `handlers/__init__.py` (lines 1079-1085), `vegetation_lsystem.py`
**Severity:** CRITICAL (actions appear to succeed but produce nothing in Blender)
**Affected actions:** `vegetation_tree`, `vegetation_leaf_cards`

**Description:** Unlike all other generators that go through `_build_quality_object` (which calls `mesh_from_spec` to create actual Blender mesh objects), the vegetation handlers are dispatched as raw pure-logic functions:

```python
# Line 1079 -- returns raw dict, never builds Blender object
"vegetation_lsystem_tree": lambda params: generate_lsystem_tree(params),
"vegetation_leaf_cards": lambda params: generate_leaf_cards(
    branch_tips=params.get("branch_tips", []), ...
),
```

`generate_lsystem_tree` and `generate_leaf_cards` are pure Python (no bpy imports). They return MeshSpec dicts with vertex/face data but never call `mesh_from_spec` or create any Blender object.

The MCP server then calls `_with_screenshot`, which returns a screenshot of the unchanged viewport plus a JSON dump of raw vertex coordinates. The user sees "success" with mesh data but no actual tree in the scene.

**Fix:** Wrap in `_build_quality_object`:
```python
"vegetation_lsystem_tree": lambda params: _build_quality_object(
    generate_lsystem_tree(params)),
```

### BUG-03: vegetation_tree sends "style" param but handler reads "tree_type" -- always generates oak
**Files:** `blender_server.py` (line 5303), `vegetation_lsystem.py` (line 642)
**Severity:** CRITICAL (user cannot select tree type)

**Description:** The server sends:
```python
# blender_server.py line 5302-5303
result = await blender.send_command("vegetation_lsystem_tree", {
    "style": _style or "oak", "seed": seed, "size": size,
})
```

But `generate_lsystem_tree` reads:
```python
# vegetation_lsystem.py line 642
tree_type = params.get("tree_type", "oak")
```

The parameter name `"style"` does not match `"tree_type"`. The tree type ALWAYS defaults to `"oak"` regardless of what the user passes as `style`. Setting `style="pine"` is silently ignored.

Additionally, the `"size"` parameter sent by the server is never read by `generate_lsystem_tree` -- it accepts parameters like `trunk_radius`, `segment_length`, and `branch_ratio` but has no `size` multiplier.

**Fix:** Either rename the server-side key to `"tree_type"`, or add a `tree_type` alias in `generate_lsystem_tree`:
```python
tree_type = params.get("tree_type", params.get("style", "oak"))
```

---

## HIGH SEVERITY BUGS

### BUG-04: Double-positioning for creature_mouth, creature_paw, creature_wing
**Files:** `handlers/__init__.py` (lines 1229-1255), `creature_anatomy.py` (generator functions)
**Severity:** HIGH (creatures appear at 2x the requested position offset)
**Affected actions:** `creature_mouth`, `creature_paw`, `creature_wing`

**Description:** These three dispatch entries pass `position` BOTH to the generator function AND to `_build_quality_object`:

```python
# Line 1242-1249 -- position applied twice
"creature_paw": lambda params: _build_quality_object(generate_paw(
    paw_type=params.get("paw_type", "canine"),
    size=params.get("size", 1.0),
    position=tuple(params.get("position", (0.0, 0.0, 0.0))),  # <-- offsets vertices
), position=tuple(params.get("position", (0.0, 0.0, 0.0)))),  # <-- sets obj.location
```

1. `generate_paw(position=(x,y,z))` adds `(x,y,z)` as offsets to every vertex coordinate
2. `_build_quality_object(spec, position=(x,y,z))` sets `obj.location = (x,y,z)`

Result: the object appears at `(2x, 2y, 2z)` instead of `(x, y, z)`. At `(0,0,0)` this is invisible, which is why it hasn't been caught.

Same pattern in:
- `creature_mouth_interior` (lines 1229-1237)
- `creature_wing` (lines 1250-1255)

Note: `creature_eyelid` passes position only to the generator, NOT to `_build_quality_object` -- no double-positioning.

**Fix:** Remove `position` from the generator call (let generator create at origin) and only pass it to `_build_quality_object`:
```python
"creature_paw": lambda params: _build_quality_object(generate_paw(
    paw_type=params.get("paw_type", "canine"),
    size=params.get("size", 1.0),
    position=(0.0, 0.0, 0.0),  # generate at origin
), position=tuple(params.get("position", (0.0, 0.0, 0.0)))),
```

### BUG-05: creature_serpent and creature_quadruped ignore server-sent position
**Files:** `blender_server.py` (lines 5217-5225), `handlers/__init__.py` (lines 1256-1270)
**Severity:** HIGH (position parameter silently ignored)

**Description:** The server sends `"position": list(pos)` for both actions:
```python
# blender_server.py line 5218-5219
result = await blender.send_command("creature_serpent_body", {
    "length": length, "size": size, "species": species, "position": list(pos),
})
```

But the handler dispatch does NOT extract or forward position:
```python
# __init__.py line 1256-1263 -- no position forwarding
"creature_serpent_body": lambda params: _build_quality_object(generate_serpent_body(
    length=params.get("length", 3.0),
    max_radius=params.get("max_radius", 0.08),
    segment_count=params.get("segment_count", 40),
    head_style=params.get("head_style", "viper"),
    include_hood=params.get("include_hood", False),
    size=params.get("size", 1.0),
)),  # <-- no position= kwarg to _build_quality_object
```

Same for `creature_quadruped` (lines 1264-1270).

The `position` from the user is transmitted all the way through the server but silently dropped at the handler dispatch. Objects always spawn at origin.

**Fix:** Add `position=tuple(params.get("position", (0.0, 0.0, 0.0)))` to `_build_quality_object()` calls.

### BUG-06: quadruped and fantasy_creature dicts missing "metadata" key -- no material assignment, wrong object name
**Files:** `creature_anatomy.py` (lines 2345-2361, 2421-2436), `_mesh_bridge.py` (lines 1008-1028), `handlers/__init__.py` (_build_quality_object lines 609-676)
**Severity:** HIGH (creatures get no procedural materials, generic object names)

**Description:** `generate_quadruped()` and `generate_fantasy_creature()` return flat dicts like:
```python
return {
    "vertices": all_verts,
    "faces": all_faces,
    "uvs": _auto_generate_uvs(all_verts),
    "species": species,
    "vertex_groups": all_groups,
    "vertex_count": len(all_verts),
    ...
}
```

These dicts have NO `"metadata"` key. In `_build_quality_object`:
- Line 622: `category = spec.get("metadata", {}).get("category", "")` -- returns `""`, so `CATEGORY_MATERIAL_MAP` lookup fails, no material assigned
- Line 628: `mesh_from_spec(spec)` reads `spec.get("metadata", {}).get("name", "MeshSpec_Object")` -- returns `"MeshSpec_Object"`, so the Blender object gets a generic name instead of species-specific name

Compare with weapons that use `_make_quality_result()` which wraps everything in proper `"metadata": {"name": ..., "category": "weapon", ...}`.

**Fix:** Add `"metadata"` dict to both generators:
```python
return {
    "vertices": all_verts,
    "faces": all_faces,
    "metadata": {
        "name": f"Quadruped_{species}",
        "category": "creature",
        "vertex_count": len(all_verts),
        "poly_count": len(all_faces),
    },
    ...
}
```

### BUG-07: riggable objects and clothing have no "category" in metadata -- no material auto-assignment
**Files:** `riggable_objects.py` (_make_riggable_result lines 63-89), `clothing_system.py` (_make_clothing_result lines 175-199)
**Severity:** HIGH (all 10 riggable props + all clothing get no procedural materials)

**Description:** `_make_riggable_result()` builds metadata as:
```python
"metadata": {
    "name": name,
    "poly_count": len(faces),
    "vertex_count": len(vertices),
    "dimensions": dims,
    "rig_info": rig_info or {},
    **extra_meta,
}
```

No `"category"` key is set, and none of the callers pass `category=...` via `**extra_meta`. Same for `_make_clothing_result()` in clothing_system.py.

In `_mesh_bridge.py`, `mesh_from_spec` looks up `CATEGORY_MATERIAL_MAP.get(category)` which returns None for `""`. Objects are created with no material -- they appear as flat white/gray in the viewport.

The CATEGORY_MATERIAL_MAP already has entries for `"riggable_prop"`, `"clothing"`, etc. -- but the generators don't set the category to match.

Actually checking the map -- there's no `"riggable_prop"` entry. The closest are `"furniture"` and `"container"`. So even with a category, doors/chains/flags wouldn't match.

**Fix:** Two changes needed:
1. Add `category="riggable_prop"` to `_make_riggable_result()` and `category="clothing"` to `_make_clothing_result()`
2. Add `"riggable_prop": "rusted_iron"` and `"clothing": "rough_timber"` (or appropriate) to `CATEGORY_MATERIAL_MAP`

---

## MEDIUM SEVERITY BUGS

### BUG-08: Texture quality actions return string, all other actions return list -- inconsistent return type
**Files:** `blender_server.py` (lines 5313-5329 vs all other actions)
**Severity:** MEDIUM (may cause downstream parsing issues)

**Description:** The three texture quality actions return `json.dumps(result, indent=2, default=str)` -- a plain string. Every other action returns `await _with_screenshot(blender, result, capture_viewport)` -- a list containing a JSON string and optionally a PNG image.

The `smart_material`, `trim_sheet`, and `macro_variation` actions also skip the `capture_viewport` parameter entirely, never taking a screenshot even if the user requested one.

**Fix:** Use consistent return format. If screenshots aren't applicable (these return code, not Blender objects), at minimum return a list with one element for consistency:
```python
return [json.dumps(result, indent=2, default=str)]
```

### BUG-09: creature_eyelid receives "eye_position" from server but position is baked into vertices without object placement
**Files:** `blender_server.py` (line 5204), `handlers/__init__.py` (lines 1238-1241)
**Severity:** MEDIUM (eyelid position works but inconsistently with other generators)

**Description:** The server sends `"eye_position": list(pos)` to `creature_eyelid_topology`. The handler dispatch forwards it as `eye_position` parameter to the generator. The generator bakes position into vertex coordinates. But `_build_quality_object` is NOT called with a `position=` kwarg, so `obj.location` stays at origin.

This means the vertices are offset but the object origin is at world origin. While the mesh appears in the right place visually, the object origin is wrong, which causes problems with:
- Rotation (rotates around world origin, not eye center)
- Scaling (scales from world origin)
- Parenting (parent offset calculated from wrong origin)

**Fix:** Either pass position only to `_build_quality_object` (not the generator), or at minimum call `bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')` after creation.

### BUG-10: vegetation_tree sends unused "size" parameter
**Files:** `blender_server.py` (line 5303), `vegetation_lsystem.py`
**Severity:** MEDIUM (user expects size to affect tree, it doesn't)

**Description:** Server sends `"size": size` to `generate_lsystem_tree()`, but the function has no `size` parameter. It reads `trunk_radius`, `segment_length`, `branch_ratio`, etc. The `size` parameter is silently ignored.

User sets `size=2.0` expecting a bigger tree, gets the exact same tree.

**Fix:** Add a `size` parameter to `generate_lsystem_tree` that multiplies `trunk_radius` and `segment_length`.

### BUG-11: object_name parameter accepted but ignored for 29 of 32 generators
**Files:** `blender_server.py` (line 5086: `object_name: str | None = None`)
**Severity:** MEDIUM (misleading API -- parameter exists but doesn't work)

**Description:** The `blender_quality` tool declares `object_name: str | None = None` as a parameter. It is only forwarded to the 3 texture quality actions (`smart_material`, `trim_sheet`, `macro_variation`). For the other 29 generators (weapons, armor, creatures, riggable, clothing, vegetation), `object_name` is silently ignored. Objects are named by their generator defaults.

**Fix:** Forward `object_name` to `_build_quality_object` or to the Blender send_command params, and have `_build_quality_object` use it to override the spec name.

### BUG-12: Vertex weld in mesh_from_spec can silently merge intentionally-separate vertices
**Files:** `_mesh_bridge.py` (lines 901-918)
**Severity:** MEDIUM (can corrupt geometry on detailed meshes)

**Description:** `mesh_from_spec` uses a vertex welding pass with `_WELD_TOLERANCE = 0.005` (5mm). Any vertices within 5mm are merged. The comment says "covers mortar gaps in stone generators" but this tolerance is applied to ALL mesh specs -- including detailed weapon cross-sections, creature anatomy, and clothing.

For weapon edge bevels (`edge_bevel` default = 0.003 = 3mm), this tolerance is LARGER than the bevel width. Edge bevel vertices that are 3mm apart will be merged into a single vertex, destroying the bevel geometry. Similarly, creature tooth geometry and clothing seam details can have vertices closer than 5mm.

The weapon generators set `edge_bevel=0.003` by default. Since 0.003 < 0.005, the bevel is always collapsed.

**Fix:** Either reduce tolerance significantly (e.g., 0.0001 = 0.1mm), make it configurable per MeshSpec, or disable welding for categories that have fine detail:
```python
_WELD_TOLERANCE = spec.get("weld_tolerance", 0.0001)
```

---

## LOW SEVERITY BUGS

### BUG-13: "Unknown action" return is a plain string, not a structured error
**Files:** `blender_server.py` (line 5331)
**Severity:** LOW (should never trigger due to Literal type constraint, but defensive coding)

**Description:** If somehow an unmatched action reaches the bottom of the function, it returns `"Unknown action"` as a bare string. Other tools return structured error dicts. Since the action type is constrained by `Literal[...]`, this should never execute, but it's inconsistent error handling.

### BUG-14: Seed parameter accepted but only forwarded to 2 of 32 generators
**Files:** `blender_server.py` (line 5078: `seed: int = 42`)
**Severity:** LOW (informational -- seed only relevant for stochastic generators)

**Description:** The `seed` parameter is only forwarded to `vegetation_tree` and `vegetation_leaf_cards`. No other generator receives or uses it. This is defensible since weapons/armor/creatures are deterministic, but the parameter's presence in the API implies it affects all generators.

Riggable objects DO use randomness internally (riggable_objects.py imports `random` and uses `_rng.Random(seed)` in `_make_plank_wall`) but with hardcoded seeds (101, 201, 202, 301, etc.) -- never receiving the user's seed.

### BUG-15: position parameter silently ignored for all weapon/armor/riggable/clothing generators
**Files:** `blender_server.py` (line 5088: `position: list[float] | None = None`)
**Severity:** LOW (weapons/armor are typically placed manually after generation)

**Description:** The `position` parameter is computed on line 5132 (`pos = tuple(position) if position else (0.0, 0.0, 0.0)`) but never forwarded to weapon, armor, riggable, or clothing generators. All 22 of these generators always create objects at origin regardless of user-specified position.

The `pos` variable itself was already flagged as unused in BUG-123 (MASTER_BUG_LIST), but the root cause -- position being accepted but not forwarded -- was not documented.

---

## PATTERN ANALYSIS: bpy.ops / bmesh / bpy.data.objects patterns

### bpy.ops without return check
The quality generator pipeline does NOT directly call `bpy.ops` -- all geometry is created via `bmesh.new()` + `bm.to_mesh()` in `mesh_from_spec`. The `bpy.ops` calls in handler files (100+ instances found) are in OTHER tools (animation_export, mesh, equipment, etc.), not in the quality generators. No new bugs in this category for the quality pipeline.

### bpy.context.active_object usage
Not used in quality generator pipeline. Only 4 instances in other handlers (mesh_enhance, objects, viewport). No new bugs.

### bpy.data.objects[name] without try/except
Not used in quality generator pipeline. The instances found are in geometry_nodes.py (generated code strings) and character_advanced.py (generated code). No new bugs for quality generators specifically.

### bmesh.from_edit_mesh without ensuring edit mode
Not used in quality generator pipeline. The 3 instances are in mesh_enhance.py (line 1210) and texture.py (lines 1594, 1611). No new bugs for quality generators.

### Missing bm.free() calls
`mesh_from_spec` (line 982) correctly calls `bm.free()` after `bm.to_mesh()`. No leak in the quality pipeline. The `_build_quality_object` function does not use bmesh directly.

---

## SUMMARY

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 3 | Creature tuple crash (5 actions), vegetation never builds objects (2 actions), tree_type parameter mismatch |
| HIGH | 4 | Double positioning (3 actions), position ignored (2 actions), missing metadata (quadruped + fantasy), missing category (riggable + clothing) |
| MEDIUM | 5 | Inconsistent return type (textures), eyelid origin wrong, size param ignored (vegetation), object_name ignored (29 actions), vertex weld destroys bevels |
| LOW | 3 | Unknown action string, seed not forwarded, position not forwarded |
| **Total** | **15** | Affecting 32 of 32 generators |

### Impact Assessment
- **7 of 32 actions will crash or produce no visible output** (5 creature anatomy + 2 vegetation)
- **10+ of 32 actions get no procedural material** (all riggable, clothing, creature, vegetation)
- **All weapons have edge bevels destroyed by vertex weld tolerance**
- **Vegetation trees always generate oak regardless of style parameter**
- **Position parameter broken in various ways across all creature actions**
