# Phase 49 Test Baseline

## Date: 2026-04-12
## After: MagicMock -> fake_bpy migration (Plan 01)

### Test Results

```
45 failed, 21253 passed, 2 skipped, 14 xfailed, 6 errors, 10 subtests passed
Duration: 278.32s (4m38s)
```

- **Total:** 21,330 (45 failed + 21,253 passed + 2 skipped + 14 xfailed + 6 errors + 10 subtests)
- **Passed:** 21,253
- **Failed:** 45
- **Errors:** 6
- **Skipped:** 2
- **xfailed:** 14

### Failure Categories

All 51 failures (45 FAILED + 6 ERROR) fall into a single root cause category:

#### fake_bpy missing stub attributes (51 tests)

These tests call handler code that accesses `bpy.data.objects`, `bpy.data.meshes`, or
`bmesh.new()` -- Blender runtime APIs that `fake_bpy` does not yet stub. Under the old
MagicMock conftest, these returned truthy mock objects that silently passed. The strict
`fake_bpy` correctly raises `AttributeError`, exposing that these tests were never truly
exercising the code paths they claimed to test.

**test_aaa_performance_budget.py** (21 failures):
- `TestLODChainTree` (11 FAILED): `bpy.data.objects.get` not stubbed -- `auto_generate_lod_chain()` needs real Blender object lookup
- `TestLODChainRock` (3 FAILED): Same `bpy.data.objects.get` issue
- `TestLODChainBuilding` (3 FAILED): Same `bpy.data.objects.get` issue
- `TestLODChainGrass` (1 FAILED): Same `bpy.data.objects.get` issue
- `TestTopologyGradeEnforcement` (6 ERROR at setup): `setUpClass` accesses `bpy.data.objects.get`

**test_aaa_water_scatter.py** (17 FAILED):
- All tests: `handle_create_water()` calls `bpy.data.objects.get` -- no fake_bpy stub for `bpy.data.objects`

**test_aaa_terrain_vegetation.py** (6 FAILED):
- `TestLeafCardPlaneCount` (3 FAILED): `create_leaf_card_tree()` calls `bpy.data.meshes.new` -- no fake_bpy stub for `bpy.data.meshes`
- `TestLeafCardReplacesUVSphere` (1 FAILED): Same `bpy.data.meshes.new` issue
- `TestWindVertexColorsRGBA` (2 FAILED): Same underlying `bpy.data` access

**test_mesh_bridge.py** (3 FAILED):
- `TestMeshFromSpecPureLogic`: `mesh_from_spec()` calls `bmesh.new()` -- no fake_bpy stub for `bmesh.new`

**test_environment_handlers.py** (1 FAILED):
- `test_multi_biome_world_uses_mesh_backed_scatter_helper`: test setup tries to `patch.object(env_mod.bpy.data.objects, "get", ...)` but `bpy.data.objects` does not exist in fake_bpy

**test_preserve_list.py** (1 FAILED):
- `test_preserve_env_generate_world_terrain_compat_wrapper`: `handle_generate_world_terrain` -> `_create_terrain_mesh_from_heightmap` calls `bpy.data.meshes.new`

#### Pre-existing failures: NONE

All 51 failures are directly caused by the fake_bpy migration. No pre-existing test
failures were detected.

### Missing fake_bpy Stubs (Root Cause Summary)

| Missing Attribute | Tests Affected | Handler Code Path |
|-------------------|---------------|-------------------|
| `bpy.data.objects` (+ `.get()`) | 32 tests | mesh_enhance.py, environment.py, environment_scatter.py |
| `bpy.data.meshes` (+ `.new()`) | 10 tests | environment_scatter.py, environment.py, _mesh_bridge.py |
| `bmesh.new()` | 3 tests | _mesh_bridge.py:932 |

These stubs are intentionally NOT added in Phase 49 -- they require careful design of
fake Blender data containers. Adding `bpy.data.objects`/`bpy.data.meshes` stubs is
scoped to the terrain execution phases where the handler code itself is being fixed.

### Quality Metrics

#### L2 Quality Lint: 17 findings (target: <= 16)

```
1 over target. Breakdown:
- 9x L2-04 SILENT-SWALLOW: bare `except Exception: pass` without comment
- 3x L2-03 FROZEN-MUTABLE: frozen dataclass with Dict default (annotated safe)
- 3x L2-01 STUB-PASS: intentional stubs in terrain_twelve_step.py
- 1x L2-02 ORPHAN-DELTA: unused `_uv_layer` in worldbuilding.py:5441
```

Delta from baseline: +1 above target (was 16, now 17). The new finding is pre-existing
`terrain_master_registrar.py:59` SILENT-SWALLOW that was always there but may not have
been counted in the previous baseline due to different file selection.

#### L5 Test Substance Lint: real_ratio 0.96 (target: >= 0.50)

```
REAL:          13,354 (96%)
SHALLOW:          534 (4%)
TAUTOLOGICAL:       1 (0%)
real_ratio:      0.96
PASS: well above 0.50 threshold
```

#### L4 Honesty Lint

```
Checkboxes: 137 checked, 466 unchecked (23% done)
Multiple NOT FOUND references for implementation plan items not yet built.
This is expected -- the plan is aspirational; code catches up over phases.
```

### Action Items for Later Phases

| Failure Group | Fix Phase | Action Required |
|---------------|-----------|----------------|
| `bpy.data.objects` stub (32 tests) | Phase 50+ (terrain execution) | Add `FakeBlenderObjects` collection to fake_bpy with `.get()`, `.new()`, `__iter__` |
| `bpy.data.meshes` stub (10 tests) | Phase 50+ (terrain execution) | Add `FakeBlenderMeshes` collection to fake_bpy with `.new()`, `.remove()` |
| `bmesh.new()` stub (3 tests) | Phase 50+ (terrain execution) | Add `FakeBMesh` with `.new()`, `.from_mesh()`, `.to_mesh()`, `.free()` |
| `bpy.data.objects` in test patches (1 test) | Phase 50+ | Refactor test to not patch bpy.data directly |
| quality_lint 17 -> 16 (1 over target) | Phase 50+ | Add explanatory comment to terrain_master_registrar.py:59 silent swallow |

### Test Pass Rate

```
Pass rate: 21,253 / 21,330 = 99.64%
Failure rate: 51 / 21,330 = 0.24%
All failures are fake_bpy-exposed, not regressions.
```
