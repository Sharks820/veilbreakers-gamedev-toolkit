# AAA 3D Pipeline

This project now treats **Stable Fast 3D** as the default local image-to-3D generator on 8 GB class GPUs, but with conservative settings to avoid VRAM spikes.

## Local backend

- Default local generator: `Stable Fast 3D`
- Fallback local generator: `SPAR3D` only after separate install and profiling. It is not treated as safe-by-default on this machine.
- Remote generation path: `Tripo` for prompt-first assets and higher-volume character generation

## Blender stack

Target studio runtime:

- `Blender 4.5 LTS` for production and agent automation
- `Blender 5.0.x` only for sandbox validation and feature trials until addon stability is proven on this machine

Core Blender stack:

- `Geometry Nodes`
- `Asset Browser`
- `Terrain Mixer`
- `A.N.T. Landscape`
- `SRTM Terrain Importer`
- `Archimesh`
- `WFC 3D Generator`
- `Bagapie`
- `Secret Paint`
- `rmKit`
- `rmKitUV`
- `UniV`
- `Mio3 UV`
- `Ucupaint`
- `TexTools`
- `Texel Density Checker`
- `LoopTools`
- `EdgeFlow`
- `Bool Tool`
- `Modifier List`
- `ND Primitives`
- `LODGen`
- `EasyMesh Batch Exporter`
- `GamiFlow`
- `BlenderKit`

Optional / experimental on this Blender build:

- `Sverchok`
- the entire `Blender 5.0.x` runtime line for automated/background tool use on this PC

## Environment

Set these env vars in `.env` or your local override file:

- `PREFERRED_3D_BACKEND=stable_fast_3d`
- `STABLE_FAST3D_REPO_PATH=<path to stable-fast-3d clone>`
- `STABLE_FAST3D_PYTHON=<path to isolated sf3d venv python>`
- `STABLE_FAST3D_DEVICE=auto`
- `STABLE_FAST3D_TEXTURE_RESOLUTION=512`
- `STABLE_FAST3D_REMESH_OPTION=triangle`
- `STABLE_FAST3D_TARGET_VERTEX_COUNT=20000`

## Bootstrap

Run:

```powershell
scripts\bootstrap_aaa_pipeline.ps1
```

That will:

- clone the Stable Fast 3D repo if needed
- write a local env override file
- write a Blender add-on manifest for the AAA stack
- optionally install Blender extensions with `-InstallBlenderExtensions`
- optionally clone GitHub add-ons with `-InstallGitAddons`

## Agent access

Agents should not guess which add-ons exist. Use:

```text
asset_pipeline action=inspect_external_toolchain
asset_pipeline action=configure_external_toolchain
```

These actions now return and persist an `agent_contract` that tells the AI:

- which Blender runtime line is active and whether it is recommended or experimental
- which terrain stack is active
- which interior/architecture stack is active
- which layout variation tools are available
- which UV, LOD, export, and QA helpers are available
- which caveats exist, such as experimental or auth-gated add-ons

The preferred preset for terrain work on this PC is:

- `agent_contract.workflow_presets.terrain_unity_ready_free`
  - `terrain_mixer -> ant_landscape/srtm helpers -> bagapie -> gamiflow -> prepare_heightmap_raw_u16 -> validation_full`

Agents and Claude should use that preset as the default free AAA terrain workflow instead of improvising the stack.

## Notes

- Stable Fast 3D is image-to-3D. It is the local path for reference-driven props, ruins, towers, and modular architectural chunks.
- Stable Fast 3D's official README says default manual inference takes about `6 GB VRAM` for a single image input. On an `8 GB` card, that leaves little headroom, so we clamp iteration defaults conservatively.
- Stable Fast 3D on Windows is officially marked **experimental** by Stability AI, so keep it in the controlled/local-helper lane rather than assuming it is production-proof.
- Use a dedicated Python 3.12 virtual environment for SF3D. Do not point it at your global Python 3.13/3.14 installs.
- SPAR3D is not enabled by default here until its repo, dependencies, and practical VRAM behavior are validated on this machine.
- Tripo remains useful for character generation and remote fallback when the local path is unavailable.
- Agents should treat `Blender 4.5 LTS` as the default studio target even if a newer Blender is installed locally.
- Blender remains the primary final-asset authoring tool. Unity should be used for assembly, terrain validation, splines, gameplay spacing, and runtime validation rather than final mesh authoring.
