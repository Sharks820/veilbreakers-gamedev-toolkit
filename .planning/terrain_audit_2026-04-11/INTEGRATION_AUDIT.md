# Terrain Audit Integration Report (2026-04-12)

Audit scope: Terrain pass pipeline (Bundles A-O), compose_map orchestration,
Unity export, handler wiring, test coverage.

---

## 1. PASS PIPELINE WIRING

### 1.1 Master Registrar Coverage

**Status: ALL 15 BUNDLE REGISTRARS WIRED**

terrain_master_registrar.py registers bundles A through O. Every registrar
function referenced in the master registrar has a matching def in its target
module. Bundle M is documented as "extension modules, no new passes" -- no
registrar expected.

### 1.2 Pass Execution Order

**Status: CORRECT for default pipeline, CALLER-DEPENDENT for full pipeline**

The default run_pipeline() sequence is:
macro_world -> structural_masks -> erosion -> validation_minimal

This respects the requires_channels DAG. The PassDAG in terrain_pass_dag.py
can compute correct topological ordering from any subset via channel edges.

### 1.3 Channel Contracts (requires vs produces)

**Status: VERIFIED for Bundle A, runtime-enforced for all bundles**

run_pass() enforces both pre-run (requires_channels present) and post-run
(produces_channels populated) via PassContractError. Strong runtime contract.

---

## 2. BAKEDTERRAIN / compose_map CONSUMPTION

### 2.1 compose_terrain_node

**Status: MISSING -- documented in MCP tool docs but NOT IMPLEMENTED**

The string compose_terrain_node appears in the MCP server system-reminder
documentation (blender_server.py line 67) but ZERO code implements it.
Any agent calling asset_pipeline action=compose_terrain_node will get
"Unknown action".

**SEVERITY: CRITICAL**

### 2.2 compose_map Terrain Path

**Status: BYPASSES PASS PIPELINE**

compose_map (blender_server.py:2957-2970) generates terrain via
env_generate_terrain -> handle_generate_terrain, which calls
generate_world_heightmap() and erode_world_heightmap() directly.
It does NOT use TerrainPassController or run_pipeline().

The pass pipeline is only accessible via env_run_terrain_pass handler
or the terrain_pipeline MCP tool.

**SEVERITY: CRITICAL** -- compose_map completely bypasses Bundle A-O quality
infrastructure (protected zones, channel contracts, checkpoints, quality gates).

### 2.3 erosion="none" Bypass

compose_map defaults erosion to True (hydraulic) via blender_server.py:2968,
so this is OK for compose_map. But handle_generate_terrain defaults to
erosion="none" when called directly via env_generate_terrain.

---

## 3. DELTA ARCHITECTURE

### 3.1 Direct Height Writes Outside Integrator

**Status: NO DEDICATED INTEGRATOR EXISTS**

7 passes call stack.set("height", ...) directly:
- _terrain_world.py:559 (pass_erosion)
- terrain_banded.py:606 (pass_banded_macro)
- terrain_framing.py:131 (pass_framing)
- terrain_glacial.py:239 (glacial pass)
- terrain_karst.py:200 (karst pass)
- terrain_wind_erosion.py:181 (wind erosion)
- coastline.py:700 (coastline shaping)
- terrain_masks.py:314 (copy only, benign)

**SEVERITY: HIGH** -- No ability to revert individual pass contributions.
Concurrent wave execution via PassDAG.execute_parallel() could race on
height if two height-producing passes end up in the same wave.

### 3.2 Cave Delta Channel -- Orphaned

terrain_caves.py:868 produces cave_height_delta but no downstream pass
reads it to integrate into height.

**SEVERITY: HIGH** -- Cave geometry deltas are computed but never applied.

---

## 4. CHANNEL CONTRACT VERIFICATION

### 4.1 Runtime Enforcement -- STRONG

PassContractError raised for missing inputs (line 195-203) and missing
outputs (line 244-253) in run_pass().

### 4.2 _ARRAY_CHANNELS Coverage -- VERIFIED

The tuple in terrain_semantics.py (lines 317-373) covers all channels
produced by passes across bundles A-O.

---

## 5. IMPORT CHAINS

### 5.1 Master Registrar Import -- WIRED CORRECTLY

Three sites call register_all_terrain_passes:
1. __init__.py:1757-1759 (module-level)
2. environment.py:1336,1359 (inside handle_run_terrain_pass)
3. Tests

### 5.2 Circular Import Risk -- MANAGED

Lazy imports in terrain_pipeline.py:403, _terrain_world.py:470,
terrain_framing.py:150 prevent circular chains. Correct.

---

## 6. UNITY EXPORT PIPELINE

### 6.1 Z-up to Y-up Conversion

**STATUS: NOT PERFORMED -- CRITICAL GAP**

terrain_unity_export.py writes coordinate_system="z-up" into the manifest
but performs NO coordinate transformation. No np.swapaxes, no Y/Z flip,
no axis remapping anywhere in the file.

terrain_unity_export_contracts.py defines required mesh attributes but
has no coordinate conversion logic either.

**SEVERITY: CRITICAL** -- Unity expects Y-up terrain data.

### 6.2 Endianness

**STATUS: IMPLICITLY CORRECT on x86**

np.save() uses native byte order (little-endian on x86). No explicit
enforcement but practically correct. The .npy header encodes endianness.

**SEVERITY: LOW**

### 6.3 Resolution Validation (2^n+1)

**STATUS: PARTIAL**

terrain_semantics.py validates height.shape == (tile_size+1, tile_size+1)
but does NOT validate that tile_size is a power of 2. A caller could set
tile_size=100 and get (101, 101) which passes but is not Unity-compatible.

**SEVERITY: MEDIUM**

---

## 7. TEST COVERAGE GAPS

### 7.1 Handler Files With No Dedicated Test File

- terrain_framing.py (only in wiring/composition tests)
- terrain_morphology.py (only in composition tests)
- terrain_hierarchy.py (only in wiring tests)
- terrain_rhythm.py (only in wiring tests)
- terrain_negative_space.py (only in wiring tests)
- terrain_sculpt.py (no test references found)
- terrain_protocol.py (no test references found)

### 7.2 No Tests for Key Functionality

- Delta integrator: no test for cave_height_delta -> height integration
- compose_terrain_node: no implementation, no tests
- Z-up to Y-up conversion: no implementation, no tests
- Power-of-2 tile_size validation: no test

---

## SUMMARY

### Critical Issues (3)

1. **compose_terrain_node is phantom** -- Documented in MCP tool description,
   zero implementation. Agents will hit "Unknown action".
   File: blender_server.py line 67 (docs only)

2. **compose_map bypasses pass pipeline** -- Calls legacy env_generate_terrain
   instead of env_run_terrain_pass. All Bundle A-O quality infrastructure unused.
   File: blender_server.py:2961, environment.py:925

3. **No Z-up to Y-up conversion in Unity export** -- Heightmap exported in
   Blender Z-up convention with no coordinate transformation.
   File: terrain_unity_export.py (entire file)

### High Issues (2)

4. **cave_height_delta produced but never consumed** -- Caves pass writes
   delta channel but nothing integrates it into height.
   File: terrain_caves.py:868

5. **Multiple passes write height directly** -- No delta integrator. 7 passes
   call stack.set("height",...) directly, making contributions non-reversible.
   Risk of race in parallel wave execution.

### Medium Issues (2)

6. **No power-of-2 validation on tile_size** -- Missing is_power_of_two check.
   File: terrain_semantics.py:401-413

7. **Test coverage gaps** -- 7+ handler files have no dedicated test file.
   Key features (delta integration, coordinate conversion) untested.

### Connected / Working (verified)

- All 15 bundle registrars wired and callable
- Channel contract enforcement is runtime-enforced via PassContractError
- PassDAG topological sort correct
- Lazy imports prevent circular dependencies
- register_all_terrain_passes called from 3 sites
- _ARRAY_CHANNELS tuple covers all produced channels
- Default pipeline order respects requires_channels DAG
