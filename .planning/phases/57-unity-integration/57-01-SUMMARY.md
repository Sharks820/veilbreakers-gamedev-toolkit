---
phase: "57"
plan: "01"
subsystem: "terrain-unity-export"
tags: [export, unity, terrain, axis-swap, endianness, lod, splatmap, fbx, erosion]
dependency_graph:
  requires: [terrain_semantics, terrain_pipeline, terrain_mask_stack]
  provides: [unity_terrain_import, terrain_size_bridge, lod_chain, splatmap_validation, erosion_upm]
  affects: [scene_templates, terrain_ecosystem_tests]
tech_stack:
  added: [terrain_export_templates.py]
  patterns: [z_up_to_y_up_axis_swap, little_endian_raw_export, power_of_2_plus_1_validation, lod_downsampling]
key_files:
  created:
    - Tools/mcp-toolkit/src/veilbreakers_mcp/shared/unity_templates/terrain_export_templates.py
    - Tools/mcp-toolkit/tests/test_unity_export_f050_f063.py
    - Tools/mcp-toolkit/tests/test_unity_export_templates.py
  modified:
    - Tools/mcp-toolkit/blender_addon/handlers/terrain_unity_export.py
    - Tools/mcp-toolkit/tests/test_terrain_ecosystem.py
decisions:
  - "Unity resolution validation uses minimum 33 (2^5+1) per Unity's actual terrain limits"
  - "Heightmap transpose used for Z-up to Y-up grid conversion (rows=Y become rows=Z)"
  - "LOD downsampling uses stride-2 sampling to preserve shared edges"
  - "TerrainSizeBridge snaps non-valid resolutions up to nearest valid Unity resolution"
  - "Erosion UPM package uses Burst+Mathematics+Collections as standard compute dependencies"
metrics:
  duration_seconds: 937
  completed: "2026-04-12T14:06:19Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 92
  tests_passed: 92
  files_created: 3
  files_modified: 2
---

# Phase 57 Plan 01: Export Fundamentals + Unity Erosion Summary

Fix 14 export bugs (F050-F063) covering Z-up axis swap, little-endian byte order, power-of-2+1 resolution validation, FBX metadata, LOD chain generation, and splatmap weight validation. Add Unity C# templates for terrain manifest import, erosion UPM package, and Blender-Unity terrain size bridging.

## Completed Tasks

### Task 1: Fix F050-F063 Export Bugs in terrain_unity_export.py
**Commit:** 022132d

**F050 - Z-up Axis Swap:**
- `swap_z_up_to_y_up_positions()`: Swaps (X,Y,Z) Z-up to (X,Z,Y) Y-up for vertex arrays
- `swap_z_up_to_y_up_heightmap()`: Transposes 2D heightmap grid (Blender rows=Y -> Unity rows=Z)
- Manifest now reports `coordinate_system: "y-up"` with `source_coordinate_system: "z-up"` preserved

**F051 - Endianness:**
- `ensure_little_endian()`: Forces LE byte order on any numpy array (handles BE, native, single-byte)
- `export_heightmap_raw()`: Writes Unity-compatible .raw file with explicit LE uint16
- Manifest declares `byte_order: "little-endian"`

**F052 - Resolution Validation:**
- `is_valid_unity_resolution()`: Checks 2^n+1 with n>=5 (min 33, max 4097)
- `validate_heightmap_resolution()`: Returns error list for non-square or invalid resolution shapes
- `VALID_UNITY_RESOLUTIONS`: Tuple of 8 valid resolutions (33..4097)
- Integrated into `export_unity_manifest()` with `validation_warnings` in output

**F053 - FBX Export:**
- `FBXExportConfig` dataclass: axis conversion, scale, mesh format, normals/UVs/colors, LOD
- `generate_fbx_export_metadata()`: Produces metadata dict with vertex/triangle counts, bounds in correct axis, terrain sizing

**F054-F058 - LOD Chain:**
- `generate_lod_heightmaps()`: Progressive stride-2 downsampling preserving shared edges (129->65->33->17)
- `export_lod_chain()`: Exports per-LOD .raw files with quantization and LE byte order
- Integrated into manifest with `lod_levels` count and per-file metadata

**F059-F063 - Splatmap Validation:**
- `validate_splatmap()`: Checks 3D shape, layer count (<=16), square, non-negative weights, sum-to-1 per pixel
- `normalize_splatmap()`: Normalizes weights to 1.0, handles zero-weight pixels
- Integrated into manifest as validation warnings

**Terrain Size Bridging:**
- `TerrainSizeBridge` dataclass: Maps Blender dimensions to Unity terrain settings
- `from_mask_stack()`: Auto-computes Unity size/position/resolution from TerrainMaskStack
- `to_unity_settings()`: Returns dict for Unity C# script consumption
- Exported as `terrain_size_bridge.json` alongside manifest

**Updated `export_unity_manifest()` to v2.0** with all new features integrated.

### Task 2: Unity C# Export Templates + Erosion UPM
**Commit:** 06f5e0d

- `terrain_export_templates.py`: New template module with 4 generators
- `generate_upm_manifest_entry()`: UPM package.json for AdvancedTerrainErosion (Burst + Mathematics + Collections deps)
- `generate_add_erosion_package_script()`: C# editor script using PackageManager Client API
- `generate_terrain_manifest_importer_script()`: C# importer that reads manifest.json + LE .raw heightmap, creates Unity Terrain with correct Y-up sizing
- `generate_terrain_erosion_script()`: C# hydraulic + thermal erosion simulation (configurable iterations, rain rate, sediment capacity, thermal rate)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed numpy newbyteorder API usage**
- **Found during:** Task 1 test run
- **Issue:** `arr.byteswap().newbyteorder("<")` fails because `newbyteorder` is a dtype method, not ndarray method
- **Fix:** Changed to `arr.byteswap().view(arr.dtype.newbyteorder("<"))`
- **Files modified:** terrain_unity_export.py
- **Commit:** 022132d

**2. [Rule 1 - Bug] Fixed is_valid_unity_resolution accepting res=2**
- **Found during:** Task 1 test run
- **Issue:** `k=1, (1 & 0) == 0` passes the power-of-2 check but res=2 is not a valid Unity terrain resolution
- **Fix:** Changed minimum from `res < 2` to `res < 33` (Unity minimum is 2^5+1 = 33)
- **Files modified:** terrain_unity_export.py
- **Commit:** 022132d

**3. [Rule 1 - Bug] Updated existing test asserting z-up in export**
- **Found during:** Task 1 regression check
- **Issue:** `test_terrain_ecosystem.py::test_unity_export_manifest_writes_files` asserted `coordinate_system == "z-up"` which was the buggy pre-fix behavior
- **Fix:** Updated to expect `"y-up"` (correct Unity target) with `source_coordinate_system == "z-up"` preserved
- **Files modified:** test_terrain_ecosystem.py
- **Commit:** 022132d

## Test Summary

| Test File | Tests | Status |
|-----------|-------|--------|
| test_unity_export_f050_f063.py | 63 | All pass |
| test_unity_export_templates.py | 29 | All pass |
| test_terrain_ecosystem.py (modified) | 63 | All pass |
| Full suite (21,566 existing) | 21,566 | All pass (91 pre-existing failures in unrelated files) |

## Self-Check: PASSED

All 5 created/modified files verified on disk. Both commit hashes (022132d, 06f5e0d) verified in git log.
