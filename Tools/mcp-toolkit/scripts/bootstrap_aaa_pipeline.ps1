param(
    [string]$StableFast3DPath = "$HOME\veilbreakers-tools\stable-fast-3d",
    [string]$EnvOut = "$PSScriptRoot\..\pipeline.local.env"
)

$ErrorActionPreference = "Stop"

Write-Host "VeilBreakers AAA 3D pipeline bootstrap"
Write-Host "Stable Fast 3D path: $StableFast3DPath"

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
    "STABLE_FAST3D_TEXTURE_RESOLUTION=1024",
    "STABLE_FAST3D_REMESH_OPTION=quad"
)

$envLines | Set-Content -Encoding UTF8 $EnvOut
Write-Host "Wrote local env override file: $EnvOut"

$manifestPath = Join-Path $PSScriptRoot "aaa_blender_addons.manifest.json"
$manifest = @"
{
  "must_install": [
    {
      "name": "Geometry Nodes",
      "source": "built-in",
      "role": "core editable world/architecture brain"
    },
    {
      "name": "Terrain Mixer",
      "source": "https://extensions.blender.org/add-ons/terrainmixer/",
      "role": "terrain/cliff authoring"
    },
    {
      "name": "A.N.T. Landscape",
      "source": "https://extensions.blender.org/add-ons/antlandscape/",
      "role": "procedural landscape blockouts"
    },
    {
      "name": "SRTM Terrain Importer",
      "source": "https://extensions.blender.org/add-ons/srtm-terrain-importer/",
      "role": "real-world heightmap import"
    },
    {
      "name": "rmKit",
      "source": "https://extensions.blender.org/add-ons/rmkit/",
      "role": "hard-surface architecture cleanup"
    },
    {
      "name": "rmKitUV",
      "source": "https://extensions.blender.org/add-ons/rmkit-uv/",
      "role": "UV editing"
    },
    {
      "name": "Ucupaint",
      "source": "https://extensions.blender.org/add-ons/ucupaint/",
      "role": "layered texture painting and baking"
    },
    {
      "name": "LoopTools",
      "source": "https://extensions.blender.org/add-ons/looptools/",
      "role": "mesh cleanup"
    },
    {
      "name": "EdgeFlow",
      "source": "https://extensions.blender.org/",
      "role": "edge flow cleanup"
    },
    {
      "name": "Bool Tool",
      "source": "https://extensions.blender.org/add-ons/bool-tool/",
      "role": "architectural boolean work"
    },
    {
      "name": "Modifier List",
      "source": "https://extensions.blender.org/add-ons/modifier-list-fork/",
      "role": "modifier stack management"
    },
    {
      "name": "BlenderKit",
      "source": "https://www.blenderkit.com/get-blender-add-ons/",
      "role": "asset/material library"
    },
    {
      "name": "MeshGen",
      "source": "https://github.com/huggingface/meshgen",
      "role": "AI control layer in Blender"
    }
  ],
  "local_ai_generation": [
    {
      "name": "Stable Fast 3D",
      "source": "https://github.com/Stability-AI/stable-fast-3d",
      "role": "default local image-to-3D generator for 8GB GPUs"
    },
    {
      "name": "SPAR3D",
      "source": "https://github.com/Stability-AI/stable-point-aware-3d",
      "role": "higher-quality fallback local generator"
    }
  ]
}
"@
$manifest | Set-Content -Encoding UTF8 $manifestPath
Write-Host "Wrote Blender add-on manifest: $manifestPath"
Write-Host "Next: set STABLE_FAST3D_REPO_PATH in your .env to $StableFast3DPath, then open Blender and install the listed add-ons."
