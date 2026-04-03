# Deep Bug Scan: Unity C# Template Generation System

**Scanned:** 2026-04-02
**Scope:** All 54 .py files in `shared/unity_templates/` (~98,200 lines) + all 24 .py files in `unity_tools/` (~9,654 lines)
**Method:** Pattern-based grep + manual code review of suspicious areas

---

## NEW BUGS FOUND: 18

### BUG-T01: `Shader.Find()` with no null-check creates NullReferenceException in combat_vfx_templates.py

**File:** `combat_vfx_templates.py` lines 425, 505, 511, 1343, 1396, 1601, 1643, 1913
**Severity:** HIGH
**Category:** Unity API error / missing null check

Every `renderer.material = new Material(Shader.Find("Universal Render Pipeline/Particles/Unlit"))` call has NO null-check on the return of `Shader.Find()`. If URP is not installed or the shader name changes, `Shader.Find()` returns `null`, and `new Material(null)` throws `ArgumentNullException`.

Some templates DO handle this correctly (e.g., `combat_spell_vfx_templates.py` lines 297-298 does `if (shader == null) shader = Shader.Find("Particles/Standard Unlit")`). But `combat_vfx_templates.py` never checks -- 8 occurrences.

**Fix:** Add null-check with fallback: `var shader = Shader.Find("Universal Render Pipeline/Particles/Unlit") ?? Shader.Find("Particles/Standard Unlit"); renderer.material = new Material(shader);`

Also affects: `evolution_templates.py` (lines 1066, 1074, 1734, 1788, 2214, 2224, 2477, 2845, 3423), `monster_vfx_templates.py` (664, 1131, 1637) -- same pattern, no null-check.

---

### BUG-T02: `renderer.material` property access in runtime code creates material leak

**File:** `combat_vfx_templates.py` lines 561-564, 586-589, 1211-1214, 1244-1247, 1298-1301, 1536-1539, 1547-1549
**Severity:** MEDIUM
**Category:** Unity API misuse / memory leak

Accessing `renderer.material` (not `renderer.sharedMaterial`) at runtime creates a material INSTANCE that must be explicitly `Destroy()`-ed. The generated code accesses `.material.SetColor()` and `.material.EnableKeyword()` without ever destroying the created instance. The project's own code reviewer (`code_review_templates.py` line 1338) flags this exact pattern as a bug.

These are in runtime MonoBehaviour methods that run every combo hit -- repeated material instance creation without cleanup = GPU memory leak.

**Fix:** Cache the material reference and destroy it in `OnDestroy()`, or use `MaterialPropertyBlock` instead (which several other templates already do correctly).

---

### BUG-T03: `audio_templates.py` -- `zone_label` unsanitized in C# class name and MenuItem

**File:** `audio_templates.py` lines 360, 367, 369
**Severity:** MEDIUM
**Category:** Unsanitized identifier in generated C#

`zone_label = zone_type.capitalize()` is used directly in:
- Class name: `VeilBreakers_AudioZone_{zone_label}` 
- MenuItem: `[MenuItem("VeilBreakers/Audio/Create {zone_label} Reverb Zone")]`

While `zone_type` typically comes from preset keys ("cave", "outdoor", etc.), the function accepts ANY string. If someone passes `zone_type="my cave"` or `zone_type="2d-room"`, the generated class name will be `VeilBreakers_AudioZone_My cave` or `VeilBreakers_AudioZone_2d-room` -- both are invalid C# identifiers causing compile errors.

**Fix:** Use `sanitize_cs_identifier(zone_label)` for the class name and `sanitize_cs_string(zone_label)` for the MenuItem string.

---

### BUG-T04: `ui_templates.py` -- `screen_name` unsanitized in MenuItem and C# string interpolation

**File:** `ui_templates.py` lines 369, 389, 403
**Severity:** MEDIUM  
**Category:** Unsanitized string in generated C#

`screen_name` is extracted from a file path (`uxml_path.split("/")[-1].replace(".uxml", "")`) and while `safe_screen_name = sanitize_cs_identifier(screen_name)` is used for the class name (line 362), the raw `screen_name` is used in:
- MenuItem string: `[MenuItem("VeilBreakers/UI/Responsive Test {screen_name}")]` -- if the filename contains `"` or `\`, the C# won't compile
- C# string interpolation: `$"{screen_name}_{{res.x}}x{{res.y}}.png"` -- unsanitized in generated C#
- JSON output: `\\\"screen\\\": \\\"{screen_name}\\\"` -- could break JSON if screen_name has quotes

**Fix:** Use `sanitize_cs_string(screen_name)` for the MenuItem and JSON, and `safe_screen_name` for the filename interpolation.

---

### BUG-T05: `vfx_templates.py` -- `brand` used raw in C# class name and MenuItem (no `sanitize_cs_identifier`)

**File:** `vfx_templates.py` lines 357, 359, 365
**Severity:** LOW (mitigated by validation against known set)
**Category:** Inconsistent sanitization

`brand` is validated against `BRAND_VFX_CONFIGS` then used raw in:
- `public static class VeilBreakers_BrandVFX_{brand}`
- `[MenuItem("VeilBreakers/VFX/Brand Damage/{brand}")]`
- `var go = new GameObject("{brand}_DamageVFX")`

Currently safe because brand is always from a fixed uppercase-alpha set. But `evolution_templates.py` uses `safe_brand = sanitize_cs_identifier(brand)` for the same pattern. This inconsistency means if a new brand with special chars is added, it would break only in `vfx_templates.py`.

**Fix:** Use `sanitize_cs_identifier(brand)` consistently, as `evolution_templates.py` does.

---

### BUG-T06: `scene_templates.py` -- `prefab_paths` unsanitized in generated C# string array

**File:** `scene_templates.py` line 238
**Severity:** HIGH
**Category:** Unsanitized string in generated C#

```python
prefab_array = ", ".join(f'"{p}"' for p in prefab_paths)
```

The raw prefab paths are embedded directly in the C# string array without `sanitize_cs_string()`. If any path contains a backslash (Windows paths) or a double-quote, the generated C# will have a syntax error or produce wrong behavior.

Example: `prefab_paths=["Assets/My \"Prefab\"/test.prefab"]` generates broken C#:
`string[] prefabPaths = new string[] { "Assets/My "Prefab"/test.prefab" };`

**Fix:** `prefab_array = ", ".join(f'"{sanitize_cs_string(p)}"' for p in prefab_paths)`

---

### BUG-T07: `performance_templates.py` -- LODGroup applied to EVERY MeshRenderer indiscriminately

**File:** `performance_templates.py` lines 326-360
**Severity:** MEDIUM
**Category:** Logic error in generated code

The LOD setup script finds ALL `MeshRenderer` objects via `FindObjectsOfType<MeshRenderer>()` and adds a LODGroup to each one. It skips objects that already have LODGroup, but it does NOT skip:
- UI elements (Canvas/World Space renderers)
- Particle system renderers
- Objects with names not matching the `_LOD0/_LOD1` convention

When `_LOD1` / `_LOD2` siblings are NOT found, it falls back to assigning the SAME renderer to all LOD levels -- which makes the LODGroup do nothing useful (same mesh at every LOD level) while adding component overhead.

**Fix:** Skip objects that don't have `_LOD` siblings. Also filter by tag or layer to avoid UI/particle objects.

---

### BUG-T08: `performance_templates.py` -- Deprecated `FindObjectsOfType` used instead of `FindObjectsByType`

**File:** `performance_templates.py` line 326
**Severity:** LOW
**Category:** Deprecated Unity API

Uses `Object.FindObjectsOfType<MeshRenderer>()` which is deprecated since Unity 2023.1 in favor of `Object.FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None)`. The `world_templates.py` line 611 correctly uses the new API (`FindObjectsByType`), but `performance_templates.py` does not.

Also affects: `prefab_templates.py` lines 1320, 1329.

**Fix:** Replace with `FindObjectsByType<MeshRenderer>(FindObjectsSortMode.None)`.

---

### BUG-T09: `prefab_templates.py` -- `configure_area` records Undo on target but modifies global NavMesh state

**File:** `prefab_templates.py` lines 1754-1755
**Severity:** MEDIUM
**Category:** Logic error

```csharp
Undo.RecordObject(target, "Configure NavMesh Area");
NavMesh.SetAreaCost({area_index}, {cost}f);
```

`NavMesh.SetAreaCost()` is a STATIC method that modifies global NavMesh settings, not the `target` object. The `Undo.RecordObject(target, ...)` records changes to the target's serialized state, but `SetAreaCost` doesn't modify the target at all. This means:
1. Undo won't actually undo the area cost change
2. The target object is unnecessarily dirtied
3. The `changedAssets` list incorrectly reports the target was changed

**Fix:** Remove the Undo call (NavMesh static settings can't be undone via Undo system). Or switch to NavMeshModifierVolume on the target object for per-area cost overrides.

---

### BUG-T10: `gameplay_templates.py` -- `agent.SetDestination()` called without `isOnNavMesh` check

**File:** `gameplay_templates.py` lines 232, 250, 265, 272, 559, 2348, 2354, 2365
**Severity:** HIGH
**Category:** Unity API misuse / runtime exception

`NavMeshAgent.SetDestination()` throws `InvalidOperationException` if the agent is not on a NavMesh. The generated mob controller and patrol scripts call `agent.SetDestination()` without checking `agent.isOnNavMesh` first. The project's own code reviewer (`code_review_templates.py` line 1742) flags this exact pattern as a bug.

This affects ALL 8 `SetDestination` call sites in the generated gameplay scripts. Mob controllers that spawn before NavMesh bake completes will throw runtime exceptions.

**Fix:** Guard each `SetDestination()` with `if (agent.isOnNavMesh)`.

---

### BUG-T11: `scene_templates.py` -- Terrain heightmap byte-reading assumes little-endian RAW format

**File:** `scene_templates.py` lines 148-161
**Severity:** MEDIUM
**Category:** Portability / wrong assumption

The heightmap reader uses:
```csharp
ushort value = (ushort)(rawBytes[byteIndex] | (rawBytes[byteIndex + 1] << 8));
```

This assumes little-endian byte order (Windows RAW). However:
1. Unity's own terrain RAW export uses platform-native byte order
2. World Machine exports big-endian RAW by default (Mac byte order)
3. Gaea exports configurable byte order

There's no byte-order parameter or auto-detection. Using a big-endian heightmap produces garbled terrain (byte-swapped values) with no error message.

**Fix:** Add a `byte_order` parameter (default "little_endian") and generate the appropriate C# read code. Or add BOM/magic-number sniffing.

---

### BUG-T12: `scene_templates.py` -- Heightmap resolution not validated as power-of-two-plus-one

**File:** `scene_templates.py` line 78
**Severity:** MEDIUM
**Category:** Missing input validation

The `resolution` parameter defaults to 513, but Unity requires `heightmapResolution` to be a power-of-two-plus-one (33, 65, 129, 257, 513, 1025, 2049, 4097). Passing values like 512, 1024, or 1000 will cause Unity to silently clamp/round them, causing mismatches between the RAW file byte count and the expected height array size:

With resolution=1024 passed: Unity sets heightmap to 1025 internally, but the code reads `1024*1024*2 = 2,097,152` bytes for a `1024x1024` array, while a `1025x1025` heightmap file would have `1025*1025*2 = 2,101,250` bytes. The last row/column is left as zeros, creating a visible seam.

**Fix:** Validate that `resolution` is in `{33, 65, 129, 257, 513, 1025, 2049, 4097}` or auto-clamp to nearest valid value. Also warn when resolution doesn't match the RAW file size.

---

### BUG-T13: `combat_vfx_templates.py` -- `brand` used in MenuItem with parentheses (unsanitized)

**File:** `combat_vfx_templates.py` line 683
**Severity:** LOW
**Category:** Unsanitized string in MenuItem

```python
[MenuItem("VeilBreakers/VFX/Setup Combo VFX ({brand})")]
```

While `brand` is constrained by validation (the function uses `safe_brand` for the class name via `sanitize_cs_identifier`), the raw `brand` is embedded in the MenuItem path. The parentheses around `{brand}` are fine, but `brand` itself could theoretically contain `/` or `"` which would break the MenuItem path hierarchy or string literal.

The same pattern appears in `evolution_templates.py` (773, 1696) and `vfx_skill_compositions.py` (770, 1256, 1948).

**Fix:** Use `sanitize_cs_string(brand)` in all MenuItem paths.

---

### BUG-T14: `editor_templates.py` -- Screenshot JSON has mismatched escape producing malformed JSON

**File:** `editor_templates.py` line 156
**Severity:** MEDIUM
**Category:** String formatting bug

The generated JSON string:
```python
string json = "{{\\"status\\": \\"success\\", \\"action\\": \\"screenshot\\", \\"path\\": \\"" + fullPath.Replace("\\\\", "/") + "\\", \\"supersize\\": " + supersizeFactor + "}}";
```

After Python f-string expansion, the C# code becomes:
```csharp
string json = "{\"status\": \"success\", \"action\": \"screenshot\", \"path\": \"" + fullPath.Replace("\\", "/") + "\", \"supersize\": " + supersizeFactor + "}";
```

The `+ "\", \"supersize\":"` part has `\"` after the path value. If `fullPath` ends with a backslash (unlikely for a path but possible), the `Replace` handles it. However, the real issue is that `fullPath.Replace("\\", "/")` only replaces backslashes with forward slashes -- it does NOT escape double quotes in the path. If the Unity path somehow contains a double quote, the JSON breaks.

Same pattern at line 345 for gemini_review.

**Fix:** Add `.Replace("\"", "\\\"")` after the `.Replace("\\", "/")` to ensure valid JSON.

---

### BUG-T15: `audio_middleware_templates.py` -- `_occlusionHits` shared static buffer causes data race

**File:** `audio_middleware_templates.py` line 83
**Severity:** MEDIUM
**Category:** Thread safety / logic error in generated code

```csharp
private static readonly RaycastHit[] _occlusionHits = new RaycastHit[16];
```

This is a `static` buffer shared across ALL instances of the generated spatial audio class. If two audio sources call `UpdateOcclusion()` in the same frame, `Physics.RaycastNonAlloc` writes into the same buffer simultaneously. The second call's `hitCount` may overwrite the first's buffer before it's read.

With the secondary rays (lines 113-114), `_occlusionHits` is reused even within a SINGLE `UpdateOcclusion()` call -- the secondary ray writes overwrite the primary ray's results, and then `hitCount = Mathf.Max(hitCount, offsetHitCount)` only tracks the count, not the actual hit data.

**Fix:** Make `_occlusionHits` an instance field (not `static`) or allocate per-instance. Also, the secondary rays should not reuse the same buffer as the primary ray within one call.

---

### BUG-T16: `world_templates.py` -- `generate_scene_creation_script` discards sanitized namespace return value

**File:** `world_templates.py` line 188
**Severity:** LOW
**Category:** Unused expression / copy-paste leftover

```python
sanitize_cs_identifier(namespace.replace(".", "_"))
```

This line (188) calls `sanitize_cs_identifier` but discards the return value -- it's a no-op expression. The actual namespace sanitization happens via `_safe_namespace(namespace)` on line 206. This appears to be a dead code remnant from an earlier version where the return was assigned.

Same pattern at line 280 in `generate_scene_transition_script`.

**Fix:** Remove the dead expressions on lines 188 and 280.

---

### BUG-T17: `combat_vfx_templates.py` -- Generated `_brand_colors_cs_dict` helper iterates ALL brands but combo VFX only uses one

**File:** `combat_vfx_templates.py` lines 65-72
**Severity:** LOW
**Category:** Inefficiency in generated code

The `_brand_colors_cs_dict` helper generates a `Dictionary<string, Color>` containing ALL 10 brands' colors, even though the combo VFX is generated for a single specific brand. This is ~500 bytes of Dictionary initialization code per generated script that's largely unused.

This is not a correctness bug but generates unnecessary code in every VFX script. The brand-specific fields (like `currentBrand = "{brand}"`) make the dictionary lookup unnecessary for the default case.

**Fix:** Only emit the dictionary for the specific brand, or use the brand-specific fields instead.

---

### BUG-T18: `shader_templates.py` / `world_templates.py` / `data_templates.py` / `content_templates.py` / `build_templates.py` / `equipment_templates.py` / `game_templates.py` -- `_CS_RESERVED` and `_safe_namespace` duplicated in 8+ files

**File:** Multiple files (world_templates.py:45, data_templates.py:33, content_templates.py:49, build_templates.py:29, shader_templates.py:51, equipment_templates.py:33, game_templates.py, gameplay_templates.py)
**Severity:** LOW (known)
**Category:** Code duplication

**NOTE:** This is listed as a known bug (_CS_RESERVED duplication). Including here only to document that the count is actually **8+ files**, not just the original 2 identified. The `_safe_namespace` function is copy-pasted identically in at least 8 template files, and `_CS_RESERVED` is duplicated in at least 8 files. If any update is needed (e.g., adding C# 12 keywords like `scoped`, `required`, `file`), all copies must be updated independently.

**Fix:** (Already known) Extract to `_cs_sanitize.py` alongside the existing helpers.

---

## Summary by Severity

| Severity | Count | Bug IDs |
|----------|-------|---------|
| HIGH | 3 | T01, T06, T10 |
| MEDIUM | 8 | T02, T03, T04, T07, T09, T11, T12, T15 |
| LOW | 7 | T05, T08, T13, T14, T16, T17, T18 |

## Categories

| Category | Count |
|----------|-------|
| Unity API misuse / missing null check | 3 (T01, T02, T10) |
| Unsanitized input in generated C# | 5 (T03, T04, T05, T06, T13) |
| Logic error in generated code | 3 (T07, T09, T15) |
| Missing input validation | 1 (T12) |
| Deprecated API | 1 (T08) |
| String formatting / JSON bug | 1 (T14) |
| Portability | 1 (T11) |
| Dead code / inefficiency | 3 (T16, T17, T18) |

## Files with Most Bugs

| File | Bug Count |
|------|-----------|
| `combat_vfx_templates.py` | 3 (T01, T02, T13) |
| `scene_templates.py` | 2 (T06, T11, T12) |
| `gameplay_templates.py` | 1 (T10) |
| `performance_templates.py` | 2 (T07, T08) |
| `audio_templates.py` | 1 (T03) |
| `ui_templates.py` | 1 (T04) |
| `vfx_templates.py` | 1 (T05) |
| `prefab_templates.py` | 1 (T09) |
| `editor_templates.py` | 1 (T14) |
| `audio_middleware_templates.py` | 1 (T15) |
| `world_templates.py` | 1 (T16) |

## Specific Question Answers

### Does generated terrain setup code correctly handle 1025x1025 heightmaps?
**NO.** Bug T12: Resolution is not validated to be power-of-two-plus-one. Passing 1024 instead of 1025 causes silent data mismatch. Bug T11: Byte order is assumed little-endian without configuration.

### Does generated LODGroup code correctly set transition percentages?
**PARTIALLY.** The percentages themselves are correct (default [0.6, 0.3, 0.15], validated as strictly descending). But Bug T07: The LODGroup is applied to every mesh indiscriminately, and when LOD siblings don't exist, the same renderer is assigned to all levels.

### Does generated NavMesh code use new AI Navigation 2.0 API or deprecated legacy?
**MIXED.** `scene_templates.py` uses `NavMeshSurface` (from `Unity.AI.Navigation` -- correct v2 API). `prefab_templates.py` uses both old (`NavMeshObstacle`, `NavMesh.SetAreaCost`) and new (`NavMeshLink`, `NavMeshModifier` from `Unity.AI.Navigation`). The `add_link` and `add_modifier` operations correctly import `Unity.AI.Navigation`, while `add_obstacle` and `configure_area` only import `UnityEngine.AI`.

### Do generated shaders use SRP Batcher compatible property blocks?
**YES.** All shader templates in `shader_templates.py` correctly use `CBUFFER_START(UnityPerMaterial)` / `CBUFFER_END` blocks for per-material properties, which is the requirement for SRP Batcher compatibility. The corruption shader (line 165-172), dissolve shader, and all other generated shaders follow this pattern correctly.
