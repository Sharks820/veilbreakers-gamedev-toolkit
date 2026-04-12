"""Tests for terrain runtime Unity C# template generators (57-03).

Covers all 7 RT-series generators:
- RT-01: Terrain deformation
- RT-02: Terrain decal spawner
- RT-03: Terrain minimap
- RT-04: FBX/LOD import chain
- RT-05: Vegetation TreePrototype
- RT-06: NavMesh terrain bake
- RT-07: Terrain streaming
"""

from __future__ import annotations

import pytest

from veilbreakers_mcp.shared.unity_templates.terrain_export_templates import (
    generate_fbx_lod_import_script,
    generate_terrain_decal_script,
    generate_terrain_deformation_script,
    generate_terrain_minimap_script,
    generate_terrain_navmesh_script,
    generate_terrain_streaming_script,
    generate_vegetation_tree_prototype_script,
)


# ---------------------------------------------------------------------------
# RT-01: Terrain Deformation
# ---------------------------------------------------------------------------


class TestTerrainDeformation:
    """RT-01: Runtime terrain heightmap deformation."""

    def test_generates_csharp_class(self):
        script = generate_terrain_deformation_script()
        assert "class VB_TerrainDeformation" in script
        assert "MonoBehaviour" in script

    def test_deform_mode_enum(self):
        script = generate_terrain_deformation_script()
        assert "enum DeformMode" in script
        assert "Raise" in script
        assert "Lower" in script
        assert "Flatten" in script
        assert "Smooth" in script

    def test_default_brush_radius(self):
        script = generate_terrain_deformation_script(brush_radius=10.0)
        assert "10f" in script or "10.0f" in script

    def test_deform_method_exists(self):
        script = generate_terrain_deformation_script()
        assert "public void Deform(" in script
        assert "Vector3 worldPos" in script
        assert "DeformMode mode" in script

    def test_undo_support(self):
        script = generate_terrain_deformation_script()
        assert "public bool Undo()" in script
        assert "_undoStack" in script

    def test_undo_stack_size_configurable(self):
        script = generate_terrain_deformation_script(undo_stack_size=20)
        assert "20" in script

    def test_uses_active_terrain(self):
        script = generate_terrain_deformation_script()
        assert "Terrain.activeTerrain" in script

    def test_heightmap_get_set(self):
        script = generate_terrain_deformation_script()
        assert "GetHeights(" in script
        assert "SetHeights(" in script

    def test_quadratic_falloff(self):
        script = generate_terrain_deformation_script()
        assert "falloff * falloff" in script

    def test_clamp01_heights(self):
        script = generate_terrain_deformation_script()
        assert "Clamp01" in script

    def test_smooth_passes_configurable(self):
        script = generate_terrain_deformation_script(smooth_passes=5)
        assert "smoothPasses = 5" in script

    def test_invalid_brush_radius_raises(self):
        with pytest.raises(ValueError, match="brush_radius"):
            generate_terrain_deformation_script(brush_radius=0)

    def test_invalid_max_depth_raises(self):
        with pytest.raises(ValueError, match="max_depth"):
            generate_terrain_deformation_script(max_depth=-1)

    def test_invalid_undo_stack_raises(self):
        with pytest.raises(ValueError, match="undo_stack_size"):
            generate_terrain_deformation_script(undo_stack_size=0)

    def test_no_unity_editor_import(self):
        """Runtime script must NOT use UnityEditor."""
        script = generate_terrain_deformation_script()
        assert "using UnityEditor" not in script


# ---------------------------------------------------------------------------
# RT-02: Terrain Decal Spawner
# ---------------------------------------------------------------------------


class TestTerrainDecalSpawner:
    """RT-02: Terrain-aware URP decal pool."""

    def test_generates_csharp_class(self):
        script = generate_terrain_decal_script()
        assert "class VB_TerrainDecalSpawner" in script
        assert "MonoBehaviour" in script

    def test_uses_urp_decal_projector(self):
        script = generate_terrain_decal_script()
        assert "DecalProjector" in script
        assert "UnityEngine.Rendering.Universal" in script

    def test_object_pool(self):
        script = generate_terrain_decal_script()
        assert "_pool" in script
        assert "Queue<DecalProjector>" in script

    def test_spawn_method(self):
        script = generate_terrain_decal_script()
        assert "public DecalProjector SpawnDecal(" in script
        assert "Vector3 worldPos" in script

    def test_terrain_normal_alignment(self):
        script = generate_terrain_decal_script()
        assert "GetInterpolatedNormal" in script

    def test_splatmap_awareness(self):
        script = generate_terrain_decal_script()
        assert "GetAlphamaps" in script
        assert "preferredSplatLayer" in script

    def test_auto_fade(self):
        script = generate_terrain_decal_script()
        assert "fadeFactor" in script
        assert "fadeDuration" in script

    def test_max_decals_configurable(self):
        script = generate_terrain_decal_script(max_decals=200)
        assert "maxActive = 200" in script

    def test_default_lifetime(self):
        script = generate_terrain_decal_script(decal_lifetime=60.0)
        assert "60" in script

    def test_recycles_oldest(self):
        """When pool empty, oldest active decal is recycled."""
        script = generate_terrain_decal_script()
        assert "_active[0]" in script
        assert "RemoveAt(0)" in script

    def test_invalid_max_decals_raises(self):
        with pytest.raises(ValueError, match="max_decals"):
            generate_terrain_decal_script(max_decals=0)

    def test_invalid_lifetime_raises(self):
        with pytest.raises(ValueError, match="decal_lifetime"):
            generate_terrain_decal_script(decal_lifetime=-1)

    def test_random_rotation(self):
        script = generate_terrain_decal_script()
        assert "Random.Range(0f, 360f)" in script


# ---------------------------------------------------------------------------
# RT-03: Terrain Minimap
# ---------------------------------------------------------------------------


class TestTerrainMinimap:
    """RT-03: Terrain-integrated minimap camera."""

    def test_generates_csharp_class(self):
        script = generate_terrain_minimap_script()
        assert "class VB_TerrainMinimap" in script
        assert "MonoBehaviour" in script

    def test_orthographic_camera(self):
        script = generate_terrain_minimap_script()
        assert "orthographic = true" in script

    def test_render_texture_creation(self):
        script = generate_terrain_minimap_script()
        assert "new RenderTexture(" in script
        assert "ARGB32" in script

    def test_follows_player_tag(self):
        script = generate_terrain_minimap_script(follow_tag="Hero")
        assert "Hero" in script
        assert "FindGameObjectWithTag" in script

    def test_terrain_height_sampling(self):
        script = generate_terrain_minimap_script()
        assert "SampleHeight" in script

    def test_compass_rotation(self):
        script = generate_terrain_minimap_script()
        assert "compassNeedle" in script
        assert "eulerAngles.y" in script

    def test_zoom_configurable(self):
        script = generate_terrain_minimap_script(zoom=120.0)
        assert "120" in script

    def test_set_zoom_method(self):
        script = generate_terrain_minimap_script()
        assert "public void SetZoom(" in script

    def test_render_texture_cleanup(self):
        script = generate_terrain_minimap_script()
        assert "OnDestroy" in script
        assert "Release()" in script

    def test_camera_height_configurable(self):
        script = generate_terrain_minimap_script(camera_height=300.0)
        assert "300" in script

    def test_update_interval(self):
        script = generate_terrain_minimap_script(update_interval=5)
        assert "updateInterval = 5" in script

    def test_invalid_render_size_raises(self):
        with pytest.raises(ValueError, match="render_size"):
            generate_terrain_minimap_script(render_size=16)

    def test_culling_mask_terrain(self):
        script = generate_terrain_minimap_script()
        assert '"Terrain"' in script

    def test_get_render_texture_accessor(self):
        script = generate_terrain_minimap_script()
        assert "GetRenderTexture()" in script


# ---------------------------------------------------------------------------
# RT-04: FBX/LOD Import Chain
# ---------------------------------------------------------------------------


class TestFBXLODImport:
    """RT-04: Import terrain FBX with LODGroup."""

    def test_generates_csharp_class(self):
        script = generate_fbx_lod_import_script()
        assert "class VeilBreakers_FBXLODImport" in script

    def test_has_menu_item(self):
        script = generate_fbx_lod_import_script()
        assert '[MenuItem("VeilBreakers/Terrain/Import FBX with LODs")]' in script

    def test_loads_fbx_asset(self):
        script = generate_fbx_lod_import_script()
        assert "LoadAssetAtPath<GameObject>" in script

    def test_creates_lod_group(self):
        script = generate_fbx_lod_import_script()
        assert "AddComponent<LODGroup>()" in script
        assert "SetLODs(" in script

    def test_custom_fbx_path(self):
        script = generate_fbx_lod_import_script(fbx_path="Assets/Custom/mesh.fbx")
        assert "Assets/Custom/mesh.fbx" in script

    def test_default_lod_distances(self):
        script = generate_fbx_lod_import_script()
        assert "0.6f" in script
        assert "0.3f" in script
        assert "0.1f" in script

    def test_custom_lod_distances(self):
        script = generate_fbx_lod_import_script(lod_distances=[0.8, 0.4, 0.05])
        assert "0.8f" in script
        assert "0.4f" in script
        assert "0.05f" in script

    def test_mesh_collider_generated(self):
        script = generate_fbx_lod_import_script(generate_collider=True)
        assert "MeshCollider" in script

    def test_mesh_collider_skipped(self):
        script = generate_fbx_lod_import_script(generate_collider=False)
        assert "AddComponent<MeshCollider>" not in script

    def test_writes_result_json(self):
        script = generate_fbx_lod_import_script()
        assert "vb_result.json" in script

    def test_error_handling(self):
        script = generate_fbx_lod_import_script()
        assert "catch" in script
        assert "error" in script

    def test_recalculates_bounds(self):
        script = generate_fbx_lod_import_script()
        assert "RecalculateBounds()" in script

    def test_sorts_renderers_by_name(self):
        script = generate_fbx_lod_import_script()
        assert "OrderBy" in script


# ---------------------------------------------------------------------------
# RT-05: Vegetation TreePrototype
# ---------------------------------------------------------------------------


class TestVegetationTreePrototype:
    """RT-05: TreePrototype wiring with density scatter."""

    def test_generates_csharp_class(self):
        script = generate_vegetation_tree_prototype_script()
        assert "class VeilBreakers_VegetationTreeSetup" in script

    def test_has_menu_item(self):
        script = generate_vegetation_tree_prototype_script()
        assert '[MenuItem("VeilBreakers/Terrain/Setup Tree Prototypes")]' in script

    def test_creates_tree_prototypes(self):
        script = generate_vegetation_tree_prototype_script()
        assert "TreePrototype" in script
        assert "treePrototypes" in script

    def test_scatters_tree_instances(self):
        script = generate_vegetation_tree_prototype_script()
        assert "TreeInstance" in script
        assert "treeInstances" in script

    def test_custom_prefab_paths(self):
        paths = ["Assets/Trees/Oak.prefab", "Assets/Trees/Birch.prefab"]
        script = generate_vegetation_tree_prototype_script(tree_prefab_paths=paths)
        assert "Assets/Trees/Oak.prefab" in script
        assert "Assets/Trees/Birch.prefab" in script

    def test_density_configurable(self):
        script = generate_vegetation_tree_prototype_script(density=0.8)
        assert "0.8f" in script

    def test_height_scale_range(self):
        script = generate_vegetation_tree_prototype_script(
            min_height=0.5, max_height=1.5
        )
        assert "0.5f" in script
        assert "1.5f" in script

    def test_width_scale_range(self):
        script = generate_vegetation_tree_prototype_script(
            min_width=0.6, max_width=1.4
        )
        assert "0.6f" in script
        assert "1.4f" in script

    def test_loads_prefabs_from_asset_db(self):
        script = generate_vegetation_tree_prototype_script()
        assert "LoadAssetAtPath<GameObject>" in script

    def test_random_rotation(self):
        script = generate_vegetation_tree_prototype_script()
        assert "Random.Range(0f, 360f)" in script

    def test_terrain_height_interpolation(self):
        script = generate_vegetation_tree_prototype_script()
        assert "GetInterpolatedHeight" in script

    def test_max_tree_cap(self):
        """Should clamp tree count to prevent OOM."""
        script = generate_vegetation_tree_prototype_script()
        assert "50000" in script

    def test_writes_result_json(self):
        script = generate_vegetation_tree_prototype_script()
        assert "vb_result.json" in script

    def test_reports_prototype_count(self):
        script = generate_vegetation_tree_prototype_script()
        assert "prototypes" in script
        assert "trees_placed" in script


# ---------------------------------------------------------------------------
# RT-06: NavMesh Terrain Bake
# ---------------------------------------------------------------------------


class TestTerrainNavMesh:
    """RT-06: Terrain-specific NavMesh baking."""

    def test_generates_csharp_class(self):
        script = generate_terrain_navmesh_script()
        assert "class VeilBreakers_TerrainNavMesh" in script

    def test_has_menu_item(self):
        script = generate_terrain_navmesh_script()
        assert '[MenuItem("VeilBreakers/Terrain/Bake Terrain NavMesh")]' in script

    def test_uses_navmesh_surface(self):
        script = generate_terrain_navmesh_script()
        assert "NavMeshSurface" in script
        assert "Unity.AI.Navigation" in script

    def test_agent_radius_configurable(self):
        script = generate_terrain_navmesh_script(agent_radius=0.8)
        assert "0.8f" in script

    def test_agent_height_configurable(self):
        script = generate_terrain_navmesh_script(agent_height=3.0)
        assert "3f" in script or "3.0f" in script

    def test_max_slope_configurable(self):
        script = generate_terrain_navmesh_script(max_slope=60.0)
        assert "60f" in script or "60.0f" in script

    def test_step_height_configurable(self):
        script = generate_terrain_navmesh_script(step_height=0.6)
        assert "0.6f" in script

    def test_builds_navmesh(self):
        script = generate_terrain_navmesh_script()
        assert "BuildNavMesh()" in script

    def test_reports_triangle_count(self):
        script = generate_terrain_navmesh_script()
        assert "CalculateTriangulation" in script
        assert "triangles" in script

    def test_area_mask_layers(self):
        script = generate_terrain_navmesh_script(
            area_mask_layers={"Water": 1, "Lava": 2}
        )
        assert "Water" in script
        assert "Lava" in script

    def test_checks_active_terrain(self):
        script = generate_terrain_navmesh_script()
        assert "Terrain.activeTerrain" in script
        assert "No active terrain" in script

    def test_writes_result_json(self):
        script = generate_terrain_navmesh_script()
        assert "vb_result.json" in script

    def test_error_handling(self):
        script = generate_terrain_navmesh_script()
        assert "catch" in script


# ---------------------------------------------------------------------------
# RT-07: Terrain Streaming
# ---------------------------------------------------------------------------


class TestTerrainStreaming:
    """RT-07: Tile-based terrain streaming via Addressables."""

    def test_generates_csharp_class(self):
        script = generate_terrain_streaming_script()
        assert "class VB_TerrainStreaming" in script
        assert "MonoBehaviour" in script

    def test_uses_addressables(self):
        script = generate_terrain_streaming_script()
        assert "UnityEngine.AddressableAssets" in script
        assert "Addressables.InstantiateAsync" in script

    def test_tile_size_configurable(self):
        script = generate_terrain_streaming_script(tile_size=1000.0)
        assert "1000" in script

    def test_load_radius_configurable(self):
        script = generate_terrain_streaming_script(load_radius=2000.0)
        assert "2000" in script

    def test_unload_radius_configurable(self):
        script = generate_terrain_streaming_script(unload_radius=3000.0)
        assert "3000" in script

    def test_hysteresis_load_unload(self):
        """Load and unload radii should be different for hysteresis."""
        script = generate_terrain_streaming_script(
            load_radius=1000, unload_radius=1500
        )
        assert "loadRadius = 1000" in script
        assert "unloadRadius = 1500" in script

    def test_check_interval(self):
        script = generate_terrain_streaming_script(check_interval=2.0)
        assert "2f" in script or "2.0f" in script

    def test_tile_coordinate_mapping(self):
        script = generate_terrain_streaming_script()
        assert "WorldToTile" in script
        assert "TileToWorld" in script

    def test_load_queue(self):
        script = generate_terrain_streaming_script()
        assert "_loadQueue" in script
        assert "maxLoadsPerFrame" in script

    def test_unload_distant_tiles(self):
        script = generate_terrain_streaming_script()
        assert "UnloadTile" in script
        assert "ReleaseInstance" in script

    def test_loaded_tile_count_property(self):
        script = generate_terrain_streaming_script()
        assert "LoadedTileCount" in script

    def test_finds_player(self):
        script = generate_terrain_streaming_script()
        assert 'FindGameObjectWithTag("Player")' in script

    def test_invalid_tile_size_raises(self):
        with pytest.raises(ValueError, match="tile_size"):
            generate_terrain_streaming_script(tile_size=0)

    def test_invalid_load_radius_raises(self):
        with pytest.raises(ValueError, match="load_radius"):
            generate_terrain_streaming_script(load_radius=-1)

    def test_invalid_unload_less_than_load_raises(self):
        with pytest.raises(ValueError, match="unload_radius"):
            generate_terrain_streaming_script(load_radius=2000, unload_radius=1000)

    def test_no_unity_editor_import(self):
        """Runtime script must NOT use UnityEditor."""
        script = generate_terrain_streaming_script()
        assert "using UnityEditor" not in script

    def test_addressable_release_on_unload(self):
        script = generate_terrain_streaming_script()
        assert "Addressables.ReleaseInstance" in script
