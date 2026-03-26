# AAA 3D Pipeline

This project now treats **Stable Fast 3D** as the default local image-to-3D generator on 8 GB class GPUs.

## Local backend

- Default local generator: `Stable Fast 3D`
- Fallback local generator: `SPAR3D`
- Remote generation path: `Tripo` for prompt-first assets and higher-volume character generation

## Blender stack

Install these first:

- `Geometry Nodes`
- `Terrain Mixer`
- `A.N.T. Landscape`
- `SRTM Terrain Importer`
- `rmKit`
- `rmKitUV`
- `Ucupaint`
- `LoopTools`
- `EdgeFlow`
- `Bool Tool`
- `Modifier List`
- `BlenderKit`
- `MeshGen`

## Environment

Set these env vars in `.env` or your local override file:

- `PREFERRED_3D_BACKEND=stable_fast_3d`
- `STABLE_FAST3D_REPO_PATH=<path to stable-fast-3d clone>`
- `STABLE_FAST3D_TEXTURE_RESOLUTION=1024`
- `STABLE_FAST3D_REMESH_OPTION=quad`

## Bootstrap

Run:

```powershell
scripts\bootstrap_aaa_pipeline.ps1
```

That will:

- clone the Stable Fast 3D repo if needed
- write a local env override file
- write a Blender add-on manifest for the AAA stack

## Notes

- Stable Fast 3D is image-to-3D. It is the local path for reference-driven props, ruins, towers, and modular architectural chunks.
- Tripo remains useful for character generation and remote fallback when the local path is unavailable.
