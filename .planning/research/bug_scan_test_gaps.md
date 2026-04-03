# Bug Scan: Test Suite Quality Audit

**Date:** 2026-04-02
**Suite:** 19,348 tests passing, 1 skipped, 5 warnings
**Scope:** Tests that pass but shouldn't, untested code paths, flaky tests, meaningless assertions

---

## EXECUTIVE SUMMARY

The test suite has impressive coverage numbers but significant structural weaknesses that explain why ~163 bugs escaped testing across 12 scan rounds. The core issue: **tests validate data structures and constants, not runtime behavior**. The bpy mock in conftest.py is so permissive (returns MagicMock for everything) that any Blender interaction code is effectively untested. Tests that claim to verify pipelines actually verify mock responses to mock inputs.

**Critical finding:** Zero integration tests exist for the `compose_map` full pipeline, `generate_prop` Tripo pipeline, multi-floor dungeon connections, LOD-to-Unity-LODGroup export, material property transfer Blender-to-Unity, or interior-exterior door alignment for non-south-facing doors. These are exactly the systems where bugs were found.

---

## MISSION 1: Tests That Pass But Shouldn't

### 1.1 The bpy MagicMock Black Hole (conftest.py)

**File:** `tests/conftest.py` lines 18-92

The entire bpy module is replaced with a `MagicMock` that returns MagicMock for any attribute access. This means:
- `bpy.data.objects["name"]` returns a MagicMock (never raises KeyError)
- `bpy.ops.mesh.primitive_cube_add()` returns a MagicMock (never fails)
- `mathutils.Vector` is a MagicMock (vector math is never computed)

**Impact:** Every test file that imports handlers touching bpy is operating in a fantasy world. The 22 test files with 253 mock/patch occurrences are testing mock plumbing, not real behavior. Files most affected:
- `test_procedural_materials.py` (46 mock references) -- material node graph builders return MagicMock nodes, assertions verify MagicMock was called, not that correct nodes were created
- `test_texture_wiring.py` (45 mock references) -- builds an elaborate mock node tree, verifies links are MagicMock-to-MagicMock
- `test_full_pipeline.py` (18 mock references) -- entire PipelineRunner is tested against canned dict responses, the actual Blender TCP protocol is never exercised

**Specific example:** `test_full_pipeline.py` line 141-148: `_make_runner()` creates a MagicMock `blender` with an `AsyncMock` `send_command` that returns hardcoded success dicts. The test verifies the PipelineRunner orchestrates calls correctly against these canned responses, but:
- Never tests what happens when `send_command` returns unexpected shapes
- Never tests what happens when the Blender connection drops mid-pipeline
- Never tests what happens when the model validation returns `valid: False`

**Verdict:** These tests verify internal orchestration logic but cannot catch bugs in the Blender communication layer, the actual bpy operations, or error edge cases.

### 1.2 Meaningless "is not None" Assertions (85 occurrences across 36 files)

**Worst offender:** `test_gameplay_templates.py` (18 occurrences)

Lines 54-252: Functions like `_validate_enemy_ai_params()`, `_validate_spawn_params()`, `_validate_ability_params()`, and `_validate_projectile_params()` are called with INVALID inputs (negative speed, negative cooldown, negative damage, etc.) and the test merely asserts `result is not None`. This is the weakest possible assertion -- it passes if the function returns `""`, `0`, `False`, `[]`, an error dict, or literally anything except `None`.

**What these tests SHOULD check:**
- That the return value contains an error message describing the validation failure
- That the error message mentions the specific invalid parameter
- That the function rejects invalid inputs rather than silently accepting them

**Other weak assertion files:**
- `test_boss_presence.py` (6 occurrences): `result["crown"] is not None` -- verifies key exists as a MagicMock, not that actual geometry was generated
- `test_mesh_bridge.py` (5 occurrences): Similar MagicMock-returns-non-None pattern
- `test_csharp_rules_audit.py` (5 occurrences): Rule existence checks, not rule behavior

### 1.3 Test That Never Actually Asserts (Dungeon Loot Points)

**File:** `test_dungeon_gen.py` lines 214-235

```python
def test_loot_points_include_secret_rooms(self):
    found_secret_loot = False
    for seed in range(100):
        layout = generate_bsp_dungeon(64, 64, seed=seed)
        secret_rooms = [r for r in layout.rooms if r.room_type == "secret"]
        if secret_rooms:
            for room in secret_rooms:
                cx, cy = room.center
                if (cx, cy) in layout.loot_points:
                    found_secret_loot = True
                    break
        if found_secret_loot:
            break
    if any(r.room_type == "secret" for s in range(100)
           for r in generate_bsp_dungeon(64, 64, seed=s).rooms):
        pass  # <-- THIS IS THE ASSERTION: `pass`
```

This test generates 200 dungeons (100 in the loop + 100 in the `any()` comprehension) and then does... `pass`. It claims to test "Secret rooms should have loot points" but NEVER ASSERTS ANYTHING. The `found_secret_loot` variable is computed but never checked. This test ALWAYS passes regardless of whether secret rooms have loot points or not.

**Bug exposure risk:** If loot point generation for secret rooms is broken, this test will not detect it.

### 1.4 Soft Assertions That Hide Failures

**File:** `test_map_composer.py` line 590:
```python
assert avg_dungeon_elev >= avg_village_elev * 0.5  # soft check
```
Multiplying by 0.5 makes this so loose that dungeons could be at half the village elevation and still pass. The comment "soft check" is a red flag -- this is essentially a no-op assertion.

**File:** `test_map_composer.py` line 138:
```python
assert -2.0 <= v <= 2.0  # allow small float overshoot
```
The docstring says "Output should be in [-1, 1]" but the assertion allows [-2, 2]. A 100% overshoot is not "small."

**File:** `test_dungeon_gen.py` lines 339-341:
```python
coverage = len(reachable) / len(town.roads)
assert coverage > 0.90, f"Road connectivity: {coverage:.2%}"
```
10% disconnected road cells are "allowed" -- this hides real connectivity bugs.

---

## MISSION 2: Untested Code Paths

### 2.1 compose_map Pipeline -- NO Integration Tests

**Source:** `blender_server.py` line 2636, `blender_addon/handlers/pipeline_state.py`, `blender_addon/handlers/addon_toolchain.py`

**Existing test coverage:**
- `test_map_composer.py` -- Tests `compose_world_map()` pure-logic function (POI placement, road generation). This is the planning layer only.
- `test_compose_planners.py` -- Tests helper functions like `_plan_map_location_anchors()`, `_resolve_map_generation_budget()`. Again planning only.
- `test_pipeline_state.py` -- Tests checkpoint save/load/resume.

**What is NOT tested:**
- The actual `compose_map` action handler in `blender_server.py` that orchestrates terrain creation, water placement, road generation, location building, vegetation scattering, and prop placement as a pipeline
- Error recovery when any pipeline step fails mid-way
- The interaction between `compose_world_map()` planning output and the actual Blender commands that create geometry
- Resume-from-checkpoint with a partially completed map

**Verdict: UNTESTED.** Known crash bugs in this pipeline had zero test coverage.

### 2.2 Tripo generate_prop -- Mocked Into Oblivion

**Source:** `blender_server.py` line 2487

**Existing test coverage:**
- `test_tripo_client.py` (121 lines) -- Tests `TripoGenerator.generate_from_text()` with fully mocked SDK. `_create_tripo_client` and `_download_file` are both patched out.
- `test_tripo_studio_client.py` (13 lines) -- Tests JWT parsing only. Two tests total.
- `test_tripo_post_processor.py` (285 lines) -- Tests post-processing (decimate, UV, material) with mocked bpy.

**What is NOT tested:**
- The `generate_prop` action handler itself (which calls TripoGenerator, imports the GLB, then post-processes)
- Error handling when Tripo returns a corrupted/invalid GLB
- Timeout handling for Tripo API calls
- The flow from `generate_prop` through post-processing to game-ready asset
- TripoStudioClient beyond JWT parsing (entire authenticated API path untested)

**Verdict: CRITICAL GAP.** Known crash bug in generate_prop had no coverage.

### 2.3 Multi-Floor Dungeon Connections -- COMPLETELY UNTESTED

**Source:** `blender_addon/handlers/_dungeon_gen.py`, `settlement_generator.py`, `worldbuilding.py`

**Existing test coverage:**
- `test_dungeon_gen.py` tests single-floor BSP dungeons extensively
- Grep for "multi_floor", "floor_connect", "staircase_connect" in test_dungeon_gen.py: **zero matches**
- Settlement generator tests mention "multi_floor" in context of building grammar, not dungeon floors

**What is NOT tested:**
- Multi-floor dungeon generation
- Staircase/ramp connections between floors
- Vertical connectivity verification (can a player path from floor 1 to floor N?)
- Floor alignment and overlap handling

**Verdict: COMPLETELY UNTESTED.** Zero tests for multi-floor dungeon systems.

### 2.4 Billboard Quad Orientation -- Partially Tested (Wrong Axis)

**Source:** `blender_addon/handlers/lod_pipeline.py`

**Existing test coverage:** `test_lod_pipeline.py` lines 698-768 (TestBillboardLOD class)
- Tests: 4 vertices, 1 face, coplanar (same Z), spans bounding box

**What is NOT tested:**
- Billboard normal direction (should face camera, i.e., +Y or -Z depending on convention)
- Billboard orientation relative to the ground plane (should be vertical, not horizontal)
- The test at line 733 checks `z_values` are all equal (coplanar in Z), which means the billboard is HORIZONTAL (lying flat on the ground). For vegetation billboards, this should be VERTICAL (standing upright). The test may be asserting the WRONG orientation.

**Verdict: TEST MAY BE WRONG.** A billboard that is coplanar in Z is lying flat -- vegetation billboards should be coplanar in Y (standing upright). This needs verification against the actual generate_lod_chain implementation.

### 2.5 LOD Export to Unity LODGroup -- Template String Check Only

**Source:** `blender_addon/handlers/lod_pipeline.py`, Unity templates

**Existing test coverage:**
- `test_functional_unity_tools.py` line 1330-1332: `assert "LODGroup" in cs` -- checks the string "LODGroup" appears in generated C# code
- `test_performance_templates.py` line 234-236: Same string check

**What is NOT tested:**
- LOD screen percentages mapping from Blender presets to Unity LODGroup.SetLODs()
- LOD mesh assignment (correct mesh to correct LOD level)
- LOD transition thresholds
- Billboard LOD handling in Unity (requires different renderer setup)
- Generated C# actually compiles and runs correctly

**Verdict: SURFACE-LEVEL ONLY.** Tests check template contains "LODGroup" string, not that LOD setup is correct.

### 2.6 Splatmap Export -- Pure Logic Tests Only

**Source:** `blender_addon/handlers/terrain_materials.py`

**Existing test coverage:** `test_terrain_materials.py` has good pure-logic tests for:
- Weight calculation and normalization (sum to 1.0)
- Moisture-aware splatmap generation
- Biome palette coverage

**What is NOT tested:**
- Actual splatmap texture/image export to a file
- Unity terrain splatmap format compatibility
- Splatmap resolution matching terrain resolution
- Channel packing (RGBA to 4 terrain layers)

**Verdict: LOGIC TESTED, EXPORT UNTESTED.**

### 2.7 Material Property Transfer Blender to Unity -- COMPLETELY UNTESTED

Grep for "material.*transfer", "transfer.*material", "blender.*unity.*material" in tests: **zero matches**.

**Source:** `blender_addon/handlers/export.py`, Unity templates

**What is NOT tested:**
- Roughness/metallic value mapping from Blender Principled BSDF to Unity Standard/URP shader
- Normal map export format (OpenGL vs DirectX convention)
- Texture path references in exported assets
- Material parameter range conversion

**Verdict: COMPLETELY UNTESTED.** No test file addresses Blender-to-Unity material transfer.

### 2.8 Settlement concentric_organic Layout -- Superficial Tests

**Source:** `blender_addon/handlers/settlement_generator.py`

**Existing test coverage:** `test_settlement_generator.py` lines 187-210:
- Checks roads have required keys (start, end, width, style)
- Checks buildings have district assignment
- Checks metadata has layout_pattern == "concentric_organic"

**What is NOT tested:**
- That buildings are actually arranged in concentric rings (not random scatter)
- Ring spacing and density
- District zone boundaries (market vs residential vs civic)
- Road network follows concentric pattern (radial + ring roads)
- Wall placement for fortified settlements

**Verdict: SCHEMA TESTED, BEHAVIOR UNTESTED.** Tests verify output dict shape, not spatial correctness.

### 2.9 Interior-Exterior Door Alignment -- South-Only Testing

**Source:** `blender_addon/handlers/_building_grammar.py`, `worldbuilding_layout.py`

**Existing test coverage:**
- `test_building_interior_binding.py` line 184-188: Tests front door faces south
- `test_building_interior_binding.py` line 199-202: Tests back door faces north
- `test_compose_planners.py` line 204: Asserts facing is in {"east", "west", "north", "south"}
- `test_worldbuilding_v2.py` lines 351-384: ALL 4 tests use `facing: "south"` hardcoded

**What is NOT tested:**
- East-facing door alignment
- West-facing door alignment
- Door position calculation for non-south-facing buildings
- Interior furniture placement relative to non-south doors (the corridor clearance test in test_interior_system.py only tests default door position)
- Building rotation affecting door world-space position

**Verdict: ONLY SOUTH/NORTH TESTED.** East/west door alignment is completely untested. The `blender_server.py` line 1074 even has a hardcoded fallback: `_derive_room_door_position(primary_room, None, "south")` -- if door metadata is missing, it always defaults to south.

---

## MISSION 3: Warnings Analysis

**5 warnings found:**

1. **ResourceWarning: unclosed socket** (`test_blender_client.py:69`) -- Socket created for connection test but not closed in teardown. Indicates missing cleanup in test fixture.

2. **ResourceWarning: unclosed file** (`test_delight.py` -- 2 warnings) -- Input/output PNG files opened via BufferedReader but never closed. File handle leak in test or production code.

3. **ResourceWarning: unclosed socket** (`test_performance_optimization.py:443`) -- Same pattern as #1.

4. **ResourceWarning: unclosed event loop** (`asyncio/base_events.py`) -- ProactorEventLoop created but not closed. The `_run()` helper in test_full_pipeline.py creates `asyncio.new_event_loop()` and closes it, but some other async test path leaks a loop.

**Impact:** These are real resource leaks. In a long-running Blender session, unclosed sockets could accumulate. In batch processing, unclosed file handles could hit OS limits.

---

## MISSION 4: Flaky Test Risk Assessment

### 4.1 Tests Using random Without Seeds

**File:** `test_map_composer.py` lines 134-137:
```python
for _ in range(100):
    x = random.uniform(-100, 100)
    y = random.uniform(-100, 100)
    v = _hash_noise_2d(x, y)
    assert -2.0 <= v <= 2.0
```
Uses module-level `random.uniform()` without setting a seed. This test is technically non-deterministic. While it's unlikely to fail (testing a wide range), the test output varies between runs.

### 4.2 np.random Without Seeds (Mostly Fixed)

The `test_coverage_gaps.py`, `test_palette_validator.py`, and `test_texture_ops.py` files all use `np.random.seed(42)` or `np.random.seed(99)` before `np.random.randint()` calls. This is correct but uses the deprecated global seed API. If another test runs between the seed and the random call, results could differ.

### 4.3 Floating Point Equality Checks

Multiple files use exact float equality (`== 0.0`, `== 1.0`, `== 0.5`) instead of `pytest.approx()`. While these are often testing hardcoded constant returns (not computed values), some are risky:

- `test_animation_handlers.py` lines 163-177: `assert result["amplitude"] == 0.8` and `assert result["glide_ratio"] == 0.3` -- if these are computed values rather than direct pass-through, floating point error could cause flakes
- `test_buildings_dungeonthemes_settlements.py` line 452: `assert result["lighting"]["fog_density"] == 0.15` -- 0.15 is not exactly representable in IEEE 754

### 4.4 File System Dependencies

- `test_pipeline_state.py` uses `tmp_path` fixture correctly
- `test_delight.py` creates files in system temp directory without cleanup (the ResourceWarning)
- `test_full_pipeline.py` line 29: Creates images in `tempfile.gettempdir()` at module load time -- could conflict between parallel test workers

### 4.5 Timing Dependencies

No obvious timing dependencies found. Async tests use proper await patterns. The socket tests in `test_blender_client.py` use mocked sockets rather than real connections.

---

## SYSTEMIC ISSUES

### Issue 1: Test Architecture Inverts the Testing Pyramid

The test suite is approximately:
- **~18,000 unit tests** on pure-logic functions (data structures, config validation, template generation)
- **~1,300 tests** on mocked Blender/Unity interactions
- **~50 tests** on actual pipeline behavior (compose_planners, pipeline_state)
- **0 integration tests** against real Blender/Unity

This means 93% of tests verify code that represents <30% of the bug surface area. The bugs found in scans live in:
1. Blender command execution (untestable without bpy)
2. Pipeline orchestration error handling (tested against mocks that never fail)
3. Cross-system data flow (Blender geometry -> export -> Unity import)
4. Runtime state (connections, sessions, file I/O)

### Issue 2: Config/Schema Tests Masquerade as Behavior Tests

Many test files verify that data dictionaries have the right keys and value types, but never verify the behavior those dictionaries drive. Examples:
- Settlement tests check buildings have "district" key but not that districts are spatially coherent
- LOD tests check presets have "ratios" key but not that decimation produces correct triangle counts
- Material tests check libraries have "base_color" key but not that colors render correctly

### Issue 3: The "Known Bug Pattern"

For each of the 9 buggy systems checked in Mission 2, the pattern is identical:
1. Pure-logic tests exist and pass (data structure shape, constant validation)
2. Integration tests for the actual pipeline DO NOT exist
3. The bug lives in the integration gap between tested components

This is not coincidental -- it's a structural problem. The test suite was built bottom-up (test each function in isolation) rather than top-down (test each user-facing pipeline end-to-end).

---

## PRIORITY FIX LIST

### P0 -- Tests That Are Actively Misleading

| File | Issue | Fix |
|------|-------|-----|
| `test_dungeon_gen.py:214-235` | `test_loot_points_include_secret_rooms` never asserts anything | Add `assert found_secret_loot` |
| `test_gameplay_templates.py` (18 tests) | `assert result is not None` on validation functions | Assert specific error messages/types |
| `test_lod_pipeline.py:723-734` | Billboard coplanar-Z may assert wrong orientation | Verify should be vertical (coplanar-Y), not horizontal |
| `test_map_composer.py:590` | `avg_dungeon_elev >= avg_village_elev * 0.5` is meaningless | Use actual elevation range constraints |

### P1 -- Missing Integration Tests (Where Bugs Live)

| System | Test Needed | Current Coverage |
|--------|-------------|------------------|
| compose_map pipeline | End-to-end with mocked Blender that validates command sequence | Zero |
| generate_prop via Tripo | Full flow: API call -> download -> import -> post-process | Mocked to nothing |
| Multi-floor dungeon | Floor generation + staircase connectivity | Zero |
| Material Blender->Unity | Property mapping + export format | Zero |
| Door alignment (E/W) | Buildings facing east/west with interior binding | Zero |
| LOD -> Unity LODGroup | Screen percentages + mesh assignment | String check only |

### P2 -- Structural Improvements

| Issue | Fix |
|-------|-----|
| 85 `is not None` assertions | Replace with specific value/type/content assertions |
| Resource leaks (5 warnings) | Add proper teardown/cleanup |
| Module-level `random` without seed | Use `random.Random(seed)` instances |
| Exact float equality | Use `pytest.approx()` for computed values |
| 0.15 fog density equality | Cannot be exact in IEEE 754 -- use approx |

### P3 -- Coverage Architecture

Create a new test category: **pipeline integration tests** that:
1. Use a "recording mock" for BlenderConnection that validates command sequences and parameter shapes
2. Inject controlled failures at each pipeline step to test error handling
3. Verify cross-system data flow (output of step N is valid input for step N+1)
4. Test compose_map, generate_prop, LOD export, and material transfer end-to-end

---

## STATISTICS

| Metric | Count |
|--------|-------|
| Total tests | 19,348 |
| Tests with `is not None` only | ~85 |
| Tests with MagicMock (potential false-pass) | ~253 references in 22 files |
| Completely untested systems (from bug list) | 4 of 9 |
| Partially tested systems | 4 of 9 |
| Adequately tested systems | 1 of 9 (compose_world_map pure logic) |
| Tests that never assert | At least 1 confirmed |
| Resource leak warnings | 5 |
| Flaky test risks | ~5 patterns identified |
