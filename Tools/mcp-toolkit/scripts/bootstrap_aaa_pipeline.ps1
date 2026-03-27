param(
    [string]$BlenderExe = "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    [string]$StableFast3DPath = "$HOME\veilbreakers-tools\stable-fast-3d",
    [string]$EnvOut = "$PSScriptRoot\..\pipeline.local.env",
    [switch]$InstallBlenderExtensions,
    [switch]$InstallGitAddons
)

$ErrorActionPreference = "Stop"

Write-Host "VeilBreakers AAA 3D pipeline bootstrap"
Write-Host "Blender executable: $BlenderExe"
Write-Host "Stable Fast 3D path: $StableFast3DPath"

if (-not (Test-Path $BlenderExe)) {
    throw "Blender executable not found at '$BlenderExe'."
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "git is required but was not found on PATH."
}

if (-not (Test-Path $StableFast3DPath)) {
    Write-Host "Cloning Stable Fast 3D..."
    git clone --depth 1 https://github.com/Stability-AI/stable-fast-3d $StableFast3DPath
} else {
    Write-Host "Stable Fast 3D already present."
}

$envLines = @(
    "# VeilBreakers AAA pipeline local overrides",
    "PREFERRED_3D_BACKEND=stable_fast_3d",
    "STABLE_FAST3D_REPO_PATH=$StableFast3DPath",
    "STABLE_FAST3D_PYTHON=$StableFast3DPath\.venv312\Scripts\python.exe",
    "STABLE_FAST3D_DEVICE=auto",
    "STABLE_FAST3D_TEXTURE_RESOLUTION=512",
    "STABLE_FAST3D_REMESH_OPTION=triangle",
    "STABLE_FAST3D_TARGET_VERTEX_COUNT=20000"
)
$envLines | Set-Content -Encoding UTF8 $EnvOut
Write-Host "Wrote local env override file: $EnvOut"

$manifestPath = Join-Path $PSScriptRoot "aaa_blender_addons.manifest.json"
$manifest = @"
{
  "built_in_foundation": [
    {"name": "Geometry Nodes", "source": "built-in", "role": "core editable world, architecture, and scatter logic"},
    {"name": "Asset Browser", "source": "built-in", "role": "shared kit parts, materials, node groups, and reusable authored assets"}
  ],
  "blender_extensions_must_install": [
    {"name": "Terrain Mixer", "module": "terrainmixer", "source": "https://extensions.blender.org/add-ons/terrainmixer/", "role": "terrain and biome authoring fallback"},
    {"name": "A.N.T. Landscape", "module": "antlandscape", "source": "https://extensions.blender.org/add-ons/antlandscape/", "role": "procedural terrain blockouts"},
    {"name": "SRTM Terrain Importer", "module": "srtm_terrain_importer", "source": "https://extensions.blender.org/add-ons/srtm-terrain-importer/", "role": "real-world terrain import"},
    {"name": "Archimesh", "module": "archimesh", "source": "https://extensions.blender.org/add-ons/archimesh/", "role": "architecture and interior blockout"},
    {"name": "Bonsai", "module": "bonsai", "source": "https://extensions.blender.org/add-ons/bonsai/", "role": "room semantics, walls, doors, slabs, and BIM-style interiors"},
    {"name": "WFC 3D Generator", "module": "wfc_3d_generator", "source": "https://extensions.blender.org/add-ons/wfc-3d-generator/", "role": "non-repeating procedural layout variation"},
    {"name": "Bagapie", "module": "Bagapie", "source": "https://extensions.blender.org/add-ons/bagapie/", "role": "scatter, ivy, random arrays, and architecture helpers"},
    {"name": "Secret Paint", "module": "secret_paint", "source": "https://extensions.blender.org/add-ons/secret-paint/", "role": "paint-driven scatter and placement workflows"},
    {"name": "Ucupaint", "module": "ucupaint", "source": "https://extensions.blender.org/add-ons/ucupaint/", "role": "layered material painting and baking"},
    {"name": "rmKit", "module": "rmKit", "source": "https://extensions.blender.org/add-ons/rmkit/", "role": "hard-surface cleanup and game-workflow helpers"},
    {"name": "rmKitUV", "module": "rmKit_uv", "source": "https://extensions.blender.org/add-ons/rmkit-uv/", "role": "UV workflow helpers"},
    {"name": "UniV", "module": "univ", "source": "https://extensions.blender.org/add-ons/univ/", "role": "advanced UV toolkit"},
    {"name": "Mio3 UV", "module": "mio3_uv", "source": "https://extensions.blender.org/add-ons/mio3-uv/", "role": "UV edit assistance"},
    {"name": "Texel Density Checker", "module": "texel_density_checker", "source": "https://extensions.blender.org/add-ons/texel-density-checker/", "role": "texel density QA"},
    {"name": "EdgeFlow", "module": "EdgeFlow", "source": "https://extensions.blender.org/add-ons/edgeflow/", "role": "edge flow and curved-surface cleanup"},
    {"name": "LoopTools", "module": "looptools", "source": "https://extensions.blender.org/add-ons/looptools/", "role": "mesh cleanup and loop editing"},
    {"name": "Bool Tool", "module": "bool_tool", "source": "https://extensions.blender.org/add-ons/bool-tool/", "role": "architectural boolean workflow"},
    {"name": "Modifier List", "module": "Modifier_List_Fork", "source": "https://extensions.blender.org/add-ons/modifier-list-fork/", "role": "modifier stack management"},
    {"name": "ND Primitives", "module": "Non_Destructive_Primitives", "source": "https://extensions.blender.org/add-ons/non-destructive-primitives/", "role": "non-destructive primitive modeling"},
    {"name": "LODGen", "module": "lod_gen", "source": "https://extensions.blender.org/add-ons/lod-gen/", "role": "LOD generation"},
    {"name": "EasyMesh Batch Exporter", "module": "easymesh_batch_exporter", "source": "https://extensions.blender.org/add-ons/easymesh-batch-exporter/", "role": "Unity-friendly batch mesh export"},
    {"name": "GamiFlow", "module": "gamiflow", "source": "https://extensions.blender.org/add-ons/gamiflow/", "role": "unwrap, bake, anchors, and export packaging"}
  ],
  "git_addons_optional": [
    {"name": "Sverchok", "module": "sverchok", "source": "https://github.com/nortikin/sverchok", "role": "advanced parametric geometry and node modeling"},
    {"name": "BlenderKit", "module": "BlenderKit", "source": "https://github.com/BlenderKit/BlenderKit", "role": "online asset and material library"},
    {"name": "TexTools-Blender", "module": "TexTools-Blender", "source": "https://github.com/franMarz/TexTools-Blender", "role": "UV, texel density, baking, and texture prep helpers"}
  ],
  "separate_apps_not_auto_installed": [
    {"name": "Material Maker", "source": "https://github.com/RodZill4/material-maker", "role": "free standalone procedural material authoring"},
    {"name": "Poly Haven", "source": "https://polyhaven.com/", "role": "CC0 HDRIs, textures, and models"},
    {"name": "ambientCG", "source": "https://ambientcg.com/", "role": "CC0 material and texture library"}
  ],
  "local_ai_generation": [
    {"name": "Stable Fast 3D", "source": "https://github.com/Stability-AI/stable-fast-3d", "role": "default local image-to-3D generator for 8GB GPUs with conservative safety defaults"},
    {"name": "SPAR3D", "source": "https://github.com/Stability-AI/stable-point-aware-3d", "role": "higher-quality fallback local generator", "status_note": "do not enable by default on this machine until dependencies and VRAM profile are validated"}
  ]
}
"@
$manifest | Set-Content -Encoding UTF8 $manifestPath
Write-Host "Wrote Blender add-on manifest: $manifestPath"

if ($InstallBlenderExtensions) {
    $extModules = @(
        "terrainmixer","antlandscape","srtm_terrain_importer","archimesh","bonsai",
        "wfc_3d_generator","Bagapie","secret_paint","ucupaint","rmKit","rmKit_uv",
        "univ","mio3_uv","texel_density_checker","EdgeFlow","looptools","bool_tool",
        "Modifier_List_Fork","Non_Destructive_Primitives","lod_gen",
        "easymesh_batch_exporter","gamiflow"
    ) -join ","
    Write-Host "Installing Blender extensions..."
    & $BlenderExe -c extension install -s -e $extModules
}

if ($InstallGitAddons) {
    $addonDir = Join-Path $env:APPDATA "Blender Foundation\Blender\5.0\scripts\addons"
    $gitAddons = @(
        @{ Repo = "https://github.com/nortikin/sverchok"; Dir = "sverchok" },
        @{ Repo = "https://github.com/BlenderKit/BlenderKit"; Dir = "BlenderKit" },
        @{ Repo = "https://github.com/franMarz/TexTools-Blender"; Dir = "TexTools-Blender" }
    )
    foreach ($addon in $gitAddons) {
        $target = Join-Path $addonDir $addon.Dir
        if (-not (Test-Path $target)) {
            Write-Host "Cloning $($addon.Dir)..."
            git clone --depth 1 $addon.Repo $target
        } else {
            Write-Host "$($addon.Dir) already present."
        }
    }
}

Write-Host "Next: run asset_pipeline action=inspect_external_toolchain and asset_pipeline action=configure_external_toolchain to sync the AI-visible toolchain contract."
