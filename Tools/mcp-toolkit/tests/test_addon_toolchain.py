from blender_addon.handlers.addon_toolchain import (
    build_agent_tool_contract,
    compute_addon_inventory,
    compute_pipeline_selection,
    normalize_toolchain_preferences,
)


def test_inventory_marks_installed_and_enabled_modules():
    inventory = compute_addon_inventory(
        installed_modules={
            "engon", "botaniq", "GeoScatter", "UVPackmaster3",
            "antlandscape", "gamiflow", "texel_density_checker",
            "BlenderKit", "sverchok", "TexTools-Blender",
        },
        enabled_modules={"engon", "GeoScatter", "gamiflow", "BlenderKit"},
    )

    assert inventory["botaniq"]["installed"] is True
    assert inventory["engon"]["enabled"] is True
    assert inventory["geo_scatter"]["installed"] is True
    assert inventory["uvpackmaster"]["installed"] is True
    assert inventory["ant_landscape"]["installed"] is True
    assert inventory["gamiflow"]["enabled"] is True
    assert inventory["texel_density_checker"]["installed"] is True
    assert inventory["blenderkit"]["enabled"] is True
    assert inventory["sverchok"]["installed"] is True
    assert inventory["textools"]["installed"] is True


def test_pipeline_selection_prefers_external_when_available():
    inventory = compute_addon_inventory(
        installed_modules={
            "engon", "botaniq", "GeoScatter", "DECALmachine",
            "UVPackmaster3", "lod_gen", "archipack", "world_creator",
            "gamiflow", "texel_density_checker", "antlandscape",
            "BlenderKit", "sverchok", "TexTools-Blender",
        },
        enabled_modules=set(),
    )

    selection = compute_pipeline_selection(inventory)

    assert selection["terrain"] == "world_creator"
    assert selection["scatter"] == "geo_scatter"
    assert selection["vegetation_assets"] == "botaniq"
    assert selection["architecture"] == "archipack"
    assert selection["surface_detail"] == "decalmachine"
    assert selection["uv"] == "uvpackmaster"
    assert selection["lod"] == "lodgen"
    assert selection["terrain_helpers"] == ["ant_landscape"]
    assert selection["export_packaging"] == "gamiflow"
    assert selection["quality_helpers"] == ["texel_density_checker", "textools"]
    assert selection["layout_helpers"] == ["sverchok"]
    assert selection["asset_sources"] == ["blenderkit"]
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

    assert selection["terrain"] == "terrain_mixer"
    assert selection["scatter"] == "bagapie"
    assert selection["vegetation_assets"] == "procedural_vegetation"
    assert selection["terrain_helpers"] == []
    assert selection["scatter_helpers"] == ["bagapie"]
    assert selection["export_packaging"] == "easymesh_batch_exporter"
    assert selection["quality_helpers"] == []
    assert selection["layout_helpers"] == ["sverchok"]
    assert selection["asset_sources"] == []
    assert selection["modeling_helpers"] == ["rmkit", "modifier_list", "sverchok"]
    assert selection["lighting_preset"] == "forest_transition"


def test_normalize_toolchain_preferences_defaults():
    prefs = normalize_toolchain_preferences({})
    assert prefs["prefer_external"] is True
    assert prefs["review_lighting"] is True
    assert prefs["project_label"] == "VeilBreakers"


def test_agent_contract_exposes_automation_targets_and_warnings():
    inventory = compute_addon_inventory(
        installed_modules={
            "bl_ext.blender_org.terrainmixer",
            "Bagapie",
            "wfc_3d_generator",
            "bonsai",
            "archimesh",
            "TexTools-Blender",
            "sverchok",
            "BlenderKit",
            "easymesh_batch_exporter",
            "texel_density_checker",
        },
        enabled_modules={"sverchok", "BlenderKit"},
    )
    selection = compute_pipeline_selection(inventory)
    contract = build_agent_tool_contract(inventory, selection)

    assert contract["automation_targets"]["terrain_authoring"] == "terrain_mixer"
    assert contract["automation_targets"]["layout_variation"] == "wfc_3d_generator"
    assert contract["automation_targets"]["interiors"] == "bonsai"
    assert contract["automation_targets"]["quality_helpers"] == ["texel_density_checker", "textools"]
    assert contract["entrypoints"]["inspect_toolchain"] == "asset_pipeline action=inspect_external_toolchain"
    assert any("Sverchok" in warning for warning in contract["warnings"])
    assert any("BlenderKit" in warning for warning in contract["warnings"])
