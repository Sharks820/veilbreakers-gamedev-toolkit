from blender_addon.handlers.addon_toolchain import (
    build_agent_tool_contract,
    compute_addon_inventory,
    compute_pipeline_selection,
    get_blender_runtime_info,
    normalize_toolchain_preferences,
)


def test_inventory_marks_installed_and_enabled_modules():
    inventory = compute_addon_inventory(
        installed_modules={
            "engon", "botaniq", "GeoScatter", "OpenScatter", "UVPackmaster3",
            "antlandscape", "gamiflow", "texel_density_checker",
            "BlenderKit", "Tripo3d_Blender_Bridge", "veilbreakers_mcp_bridge",
            "sverchok", "TexTools-Blender",
        },
        enabled_modules={
            "engon", "GeoScatter", "OpenScatter", "gamiflow",
            "BlenderKit", "Tripo3d_Blender_Bridge", "veilbreakers_mcp_bridge",
        },
    )

    assert inventory["botaniq"]["installed"] is True
    assert inventory["engon"]["enabled"] is True
    assert inventory["geo_scatter"]["installed"] is True
    assert inventory["openscatter"]["enabled"] is True
    assert inventory["uvpackmaster"]["installed"] is True
    assert inventory["ant_landscape"]["installed"] is True
    assert inventory["gamiflow"]["enabled"] is True
    assert inventory["texel_density_checker"]["installed"] is True
    assert inventory["blenderkit"]["enabled"] is True
    assert inventory["tripo_bridge"]["enabled"] is True
    assert inventory["veilbreakers_mcp_bridge"]["enabled"] is True
    assert inventory["sverchok"]["installed"] is True
    assert inventory["textools"]["installed"] is True


def test_pipeline_selection_prefers_external_when_available():
    inventory = compute_addon_inventory(
        installed_modules={
            "engon", "botaniq", "GeoScatter", "DECALmachine",
            "UVPackmaster3", "lod_gen", "archipack", "world_creator",
            "gamiflow", "texel_density_checker", "antlandscape",
            "BlenderKit", "sverchok", "TexTools-Blender", "veilbreakers_mcp_bridge",
        },
        enabled_modules={
            "GeoScatter", "DECALmachine", "UVPackmaster3", "lod_gen",
            "archipack", "world_creator", "gamiflow", "texel_density_checker",
            "antlandscape", "BlenderKit", "sverchok", "TexTools-Blender",
            "veilbreakers_mcp_bridge",
        },
    )

    selection = compute_pipeline_selection(inventory)

    assert selection["terrain"] == "world_creator"
    assert selection["scatter"] == "geo_scatter"
    assert selection["vegetation_assets"] == "procedural_vegetation"
    assert selection["architecture"] == "archipack"
    assert selection["surface_detail"] == "decalmachine"
    assert selection["uv"] == "uvpackmaster"
    assert selection["lod"] == "lodgen"
    assert selection["terrain_helpers"] == ["ant_landscape"]
    assert selection["export_packaging"] == "gamiflow"
    assert selection["quality_helpers"] == ["texel_density_checker", "textools"]
    assert selection["layout_helpers"] == ["sverchok"]
    assert selection["asset_sources"] == ["blenderkit"]
    assert selection["automation_bridge"] == "veilbreakers_mcp_bridge"
    assert selection["lighting_preset"] == "forest_review"


def test_pipeline_selection_falls_back_to_native_tools():
    inventory = compute_addon_inventory(
        installed_modules={
            "bl_ext.blender_org.terrainmixer",
            "Bagapie",
            "rmKit",
            "Modifier_List_Fork",
            "easymesh_batch_exporter",
            "sverchok",
        },
        enabled_modules=set(),
    )

    selection = compute_pipeline_selection(inventory, prefer_external=True, review_lighting=False)

    assert selection["terrain"] == "native_terrain"
    assert selection["scatter"] == "native_scatter"
    assert selection["vegetation_assets"] == "procedural_vegetation"
    assert selection["terrain_helpers"] == []
    assert selection["scatter_helpers"] == []
    assert selection["export_packaging"] == "native_export_packaging"
    assert selection["quality_helpers"] == []
    assert selection["layout_helpers"] == []
    assert selection["asset_sources"] == []
    assert selection["modeling_helpers"] == []
    assert "terrain_mixer" in selection["disabled_but_installed"]
    assert selection["automation_bridge"] == "native_bridge"
    assert selection["lighting_preset"] == "forest_transition"


def test_normalize_toolchain_preferences_defaults():
    prefs = normalize_toolchain_preferences({})
    assert prefs["prefer_external"] is True
    assert prefs["review_lighting"] is True
    assert prefs["project_label"] == "VeilBreakers"


def test_blender_runtime_info_available_or_explicitly_unavailable():
    info = get_blender_runtime_info()
    assert info["recommended_line"] == "4.5 LTS"
    assert info["available"] in (True, False)
    assert info["status"] in ("recommended", "experimental", "legacy", "unavailable")


def test_agent_contract_exposes_automation_targets_and_warnings():
    inventory = compute_addon_inventory(
        installed_modules={
            "bl_ext.blender_org.terrainmixer",
            "Bagapie",
            "OpenScatter",
            "wfc_3d_generator",
            "archimesh",
            "TexTools-Blender",
            "sverchok",
            "BlenderKit",
            "easymesh_batch_exporter",
            "texel_density_checker",
            "Tripo3d_Blender_Bridge",
            "veilbreakers_mcp_bridge",
        },
        enabled_modules={
            "OpenScatter",
            "wfc_3d_generator",
            "archimesh",
            "TexTools-Blender",
            "sverchok",
            "BlenderKit",
            "texel_density_checker",
            "Tripo3d_Blender_Bridge",
            "veilbreakers_mcp_bridge",
        },
    )
    selection = compute_pipeline_selection(inventory)
    contract = build_agent_tool_contract(
        inventory,
        selection,
        blender_runtime={"line": "5.0", "status": "experimental"},
    )

    assert contract["automation_targets"]["terrain_authoring"] == "native_terrain"
    assert contract["automation_targets"]["layout_variation"] == "wfc_3d_generator"
    assert contract["automation_targets"]["interiors"] == "archimesh"
    assert contract["automation_targets"]["scatter"] == "openscatter"
    assert contract["automation_targets"]["quality_helpers"] == ["texel_density_checker", "textools"]
    assert contract["automation_targets"]["asset_sources"] == ["blenderkit", "tripo_bridge"]
    assert contract["automation_targets"]["automation_bridge"] == "veilbreakers_mcp_bridge"
    assert contract["blender_runtime"]["status"] == "experimental"
    preset = contract["workflow_presets"]["terrain_unity_ready_free"]
    assert preset["toolchain"]["terrain_authoring"] == "terrain_mixer"
    assert preset["toolchain"]["scatter"] == "bagapie"
    assert preset["toolchain"]["export_packaging"] == "native_export_packaging"
    assert preset["terrain_pass_sequence"][-2:] == ["prepare_heightmap_raw_u16", "validation_full"]
    assert contract["entrypoints"]["inspect_toolchain"] == "asset_pipeline action=inspect_external_toolchain"
    assert any("Sverchok" in warning for warning in contract["warnings"])
    assert any("BlenderKit" in warning for warning in contract["warnings"])
    assert any("Installed but disabled addons" in warning for warning in contract["warnings"])


def test_bonsai_is_not_selected_as_active_interior_authoring():
    inventory = compute_addon_inventory(
        installed_modules={"bonsai", "archimesh"},
        enabled_modules={"bonsai", "archimesh"},
    )

    selection = compute_pipeline_selection(inventory)
    contract = build_agent_tool_contract(inventory, selection)

    assert selection["interior_authoring"] == "archimesh"
    assert contract["automation_targets"]["interiors"] == "archimesh"
    assert any("Bonsai" in warning for warning in contract["warnings"])


def test_agent_contract_does_not_warn_for_disabled_installed_online_addons():
    inventory = compute_addon_inventory(
        installed_modules={"BlenderKit", "veilbreakers_mcp_bridge"},
        enabled_modules={"veilbreakers_mcp_bridge"},
    )
    selection = compute_pipeline_selection(inventory)

    contract = build_agent_tool_contract(
        inventory,
        selection,
        blender_runtime={"line": "4.5", "status": "recommended"},
    )

    assert not any("BlenderKit" in warning for warning in contract["warnings"])
