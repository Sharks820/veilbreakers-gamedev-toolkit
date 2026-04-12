"""Tests for terrain_export_templates — Unity C# script generation.

Covers:
- UPM manifest entry for AdvancedTerrainErosion
- C# script generation for erosion package install
- C# terrain manifest importer script
- C# terrain erosion application script
"""

from __future__ import annotations

import pytest

from veilbreakers_mcp.shared.unity_templates.terrain_export_templates import (
    ADVANCED_TERRAIN_EROSION_UPM,
    generate_add_erosion_package_script,
    generate_terrain_erosion_script,
    generate_terrain_manifest_importer_script,
    generate_upm_manifest_entry,
)


class TestUPMManifestEntry:
    """UPM package manifest for AdvancedTerrainErosion."""

    def test_manifest_has_required_fields(self):
        m = generate_upm_manifest_entry()
        assert "name" in m
        assert "version" in m
        assert "displayName" in m
        assert "description" in m
        assert "unity" in m
        assert "dependencies" in m

    def test_package_name_valid(self):
        m = generate_upm_manifest_entry()
        assert m["name"].startswith("com.")
        assert "." in m["name"]

    def test_dependencies_include_burst(self):
        m = generate_upm_manifest_entry()
        deps = m["dependencies"]
        assert "com.unity.burst" in deps

    def test_dependencies_include_mathematics(self):
        m = generate_upm_manifest_entry()
        deps = m["dependencies"]
        assert "com.unity.mathematics" in deps

    def test_unity_min_version(self):
        m = generate_upm_manifest_entry()
        assert m["unity"] >= "2022.3"


class TestAddErosionPackageScript:
    """C# script to add erosion UPM package."""

    def test_generates_valid_csharp(self):
        script = generate_add_erosion_package_script()
        assert "using UnityEngine;" in script
        assert "using UnityEditor;" in script
        assert "Client.Add(" in script

    def test_contains_package_name(self):
        script = generate_add_erosion_package_script()
        assert ADVANCED_TERRAIN_EROSION_UPM["package_name"] in script

    def test_custom_package_name(self):
        script = generate_add_erosion_package_script(
            package_name="com.custom.erosion", version="2.0.0"
        )
        assert "com.custom.erosion@2.0.0" in script

    def test_writes_result_json(self):
        script = generate_add_erosion_package_script()
        assert "vb_result.json" in script

    def test_has_menu_item(self):
        script = generate_add_erosion_package_script()
        assert '[MenuItem("VeilBreakers/Terrain/Add Erosion Package")]' in script

    def test_handles_errors(self):
        script = generate_add_erosion_package_script()
        assert "catch" in script
        assert "error" in script


class TestTerrainManifestImporterScript:
    """C# script to import terrain from Blender manifest."""

    def test_generates_valid_csharp(self):
        script = generate_terrain_manifest_importer_script()
        assert "using UnityEngine;" in script
        assert "using UnityEditor;" in script

    def test_reads_manifest_json(self):
        script = generate_terrain_manifest_importer_script()
        assert "manifest.json" in script.lower() or "manifestPath" in script

    def test_imports_raw_heightmap(self):
        script = generate_terrain_manifest_importer_script()
        assert "heightmap.raw" in script

    def test_little_endian_read(self):
        """F051: Must read .raw as little-endian uint16."""
        script = generate_terrain_manifest_importer_script()
        # The LE read pattern: rawBytes[idx] | (rawBytes[idx + 1] << 8)
        assert "rawBytes[idx]" in script
        assert "<< 8" in script

    def test_y_up_coordinate_system(self):
        """F050: Manifest importer expects Y-up data."""
        script = generate_terrain_manifest_importer_script()
        assert "y-up" in script

    def test_creates_terrain_gameobject(self):
        script = generate_terrain_manifest_importer_script()
        assert "CreateTerrainGameObject" in script

    def test_sets_terrain_size(self):
        script = generate_terrain_manifest_importer_script()
        assert "terrainData.size" in script

    def test_custom_manifest_path(self):
        script = generate_terrain_manifest_importer_script(
            manifest_path="Assets/Custom/manifest.json"
        )
        assert "Assets/Custom/manifest.json" in script

    def test_has_menu_item(self):
        script = generate_terrain_manifest_importer_script()
        assert '[MenuItem("VeilBreakers/Terrain/Import from Manifest")]' in script

    def test_validation_status_reported(self):
        script = generate_terrain_manifest_importer_script()
        assert "validation_status" in script


class TestTerrainErosionScript:
    """C# script to apply erosion to Unity terrain."""

    def test_generates_valid_csharp(self):
        script = generate_terrain_erosion_script()
        assert "using UnityEngine;" in script
        assert "using UnityEditor;" in script

    def test_default_iterations(self):
        script = generate_terrain_erosion_script(iterations=50)
        assert "50 iterations" in script

    def test_custom_parameters(self):
        script = generate_terrain_erosion_script(
            iterations=100,
            rain_rate=0.02,
            sediment_capacity=0.08,
        )
        assert "100" in script
        assert "0.02f" in script
        assert "0.08f" in script

    def test_hydraulic_erosion(self):
        script = generate_terrain_erosion_script()
        assert "water" in script
        assert "sediment" in script

    def test_thermal_erosion(self):
        script = generate_terrain_erosion_script()
        assert "thermalRate" in script

    def test_checks_active_terrain(self):
        script = generate_terrain_erosion_script()
        assert "activeTerrain" in script
        assert "No active terrain" in script

    def test_writes_result_json(self):
        script = generate_terrain_erosion_script()
        assert "vb_result.json" in script

    def test_has_menu_item(self):
        script = generate_terrain_erosion_script()
        assert '[MenuItem("VeilBreakers/Terrain/Apply Erosion")]' in script
