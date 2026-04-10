# Terrain Generators: Cave / Overhang / Recessed Opening Workflows

**Research Date:** 2026-04-06
**Context:** VeilBreakers dark fantasy action RPG, Blender addon, procedural terrain pipeline
**Target problem:** Cut AAA-quality cave entrance (~10 units wide) into the top of an existing MountainPass cliff mesh (65k verts, non-manifold) under Python/bpy control.

---

## TL;DR -- Decision Matrix

| Tool | True 3D Caves? | AAA Grade? | Blender Python Pipeline? | Cost | Verdict for VB |
|---|---|---|---|---|---|
| **Gaea (QuadSpinner)** | No (heightmap) | Yes, for terrain base | Mesh export OBJ/FBX, no live API | Free/Indie/Pro/Enterprise | Use for base terrain only |
| **World Creator** | No (heightmap, voxel preview only) | Yes | Mesh export only | ~$150-$450 | Skip for caves |
| **World Machine** | No (heightmap) | Yes | Mesh export only | $149-$299 | Skip entirely (outdated) |
| **Houdini** | **Yes** (SOP/VEX/HDA) | **Yes (industry standard)** | HDA via unofficial plugin or FBX | $269/yr Indie | Overkill but gold-standard |
| **Substance 3D Modeler** | **Yes** (volumetric sculpt) | Yes | FBX export only | $19.99/mo Adobe sub | Good hero-asset path |
| **Substance Designer** | No (2D texture graph) | N/A for geom | N/A | Adobe sub | Not applicable |
| **ZBrush** | **Yes** (DynaMesh sculpt) | **Yes (AAA standard)** | FBX/OBJ export only | $399 perp / $39.95 mo | Best for hero caves |
| **Quixel Megascans** | **Yes** (photogrammetry meshes) | **Yes (photoreal)** | Fab.com API + FBX | Free with Unreal, paid on Fab | Best kitbash path |
| **Blender Boolean + SDF** | **Yes** | Yes if done right | **Native bpy** | Free | **WINNER for our use case** |
| **Blender OpenVDB / GN** | **Yes** | Yes | **Native bpy** | Free | Backup / high-quality path |

**Recommendation for the MountainPass case: Use Blender's native Boolean + sculpt path with a procedurally-generated cutter mesh, fall back to OpenVDB/SDF if booleans fail on the non-manifold input.** (See full reasoning at end.)

---

## 1. Gaea (QuadSpinner)

### 3D Cave Support
**No.** Gaea is fundamentally a heightmap tool. Its own documentation states: *"Because terrain is shaped by heightmaps, where the greyscale value of each pixel corresponds to that pixel's height in the editor, it is not possible to create overhangs. This means no caves, no overhanging cliffs, and no crystal spikes jutting out from walls or hanging over other terrain."*

Gaea has a `Crater Cave-In` technique node that simulates the *visual* of a cave collapse on the surface -- it is a crater with debris, not a 3D recess.

### Workflow for "Cave Entrance in Cliff"
Gaea does not do this. Artists use Gaea for the macro terrain (mountains, erosion, ridges, rivers), then take the result into Houdini / ZBrush / Blender to sculpt or boolean the cave in manually.

### Export to Blender
- **Formats:** OBJ, FBX, DAE, glTF via the Mesher node
- **Scales:** Normalized (0..1) or Metric
- **Tris/Quads/Adaptive Tris** (Sophia algorithm)
- Planar UVs by default
- No live API -- file-based export only. Gaea 3.0 (mid-2026) adds **USD import/export** on Professional/Enterprise editions which would allow a cleaner pipeline into Blender, but still only for terrain, not caves.

### Quality
**AAA for base terrain** (erosion is industry-leading). **Zero** for caves/overhangs.

### Cost
- Community: Free (with watermark, 1K resolution)
- Indie: Affordable, commercial-friendly
- Professional / Enterprise: Pricey, adds USD + more
Gaea 3.0 adds infinite "world-space" nodes for huge worlds.

### Python Pipeline
No Python API. Must invoke Gaea CLI / pre-baked `.terrain` files, then import the resulting mesh/heightmap into Blender through `bpy.ops.import_scene.fbx` or `bpy.ops.import_scene.obj`.

**Use case for VB:** Generate macro terrain + erosion masks in Gaea (offline), import into Blender as heightmap or mesh, then use Blender tools for caves.

---

## 2. World Creator

### 3D Cave Support
**No.** World Creator is also heightmap-based at its core. The official documentation openly acknowledges that "voxel systems can represent features that heightmaps cannot -- such as caves, tunnels, overhangs, floating islands, and fully destructible environments." World Creator is a heightmap tool.

Mesh export is available but is a direct polygon version of the heightmap -- it carries the same overhang limitation.

### Workflow
Users build the heightmap terrain, export as mesh, then add caves as separate kitbashed meshes in a DCC.

### Export to Blender
Mesh export (OBJ/FBX). Note: a 1024x1024 terrain is ~2 MB as heightmap vs ~56 MB as mesh -- heightmap is preferred except when needed for sculpting.

### Quality
AAA for terrain base, not applicable for caves.

### Cost
~$150 Standard, up to ~$450 for Pro editions (perpetual).

### Python Pipeline
No direct Python. File export only.

**Verdict:** Same conclusion as Gaea -- good for base, nothing for caves.

---

## 3. World Machine

### 3D Cave Support
**No.** World Machine is the oldest of the three and most constrained to heightmaps. Community workarounds:
1. **Multiple heightmaps** -- Base + overhang + ceiling layer, combined at render time (fragile, requires engine support).
2. **Mesh + hole punch** -- Export base heightmap, cut a hole in the terrain, drop in a separate cave mesh modeled elsewhere.
3. **Mesh Output device** -- export polygons instead of heightmap, modify downstream.

### Workflow
Community has converged on: export World Machine mesh, then sculpt caves in Blender/ZBrush.

### Cost
$149 Standard / $299 Pro (perpetual).

### Verdict
**Skip.** World Machine is superseded by Gaea for new projects. Nothing it does is unique to our pipeline.

---

## 4. Houdini (SideFX)

### 3D Cave Support
**Yes -- this is where professional procedural caves live.**

Techniques used:
- **Voronoi Fracture SOP** -- break a solid volume into cells that feel cave-like; assign labels (wall/ceiling/floor) via VEX wrangles (`nuniqueval`, `uniqueval`)
- **VEX wrangles** for noise-driven deformation of the cell walls
- **HeightField + Volume workflows** for hybrid 2.5D terrain + 3D recesses
- **Project Grot** (SideFX tech demo, 2025) is a proof-of-concept cave environment built entirely in Houdini procedurally and exported to Unreal 5
- **PolyExtrude / Boolean SOPs** for direct mesh cave cutters
- **Metaballs / SDF volumes** for organic cave tube generation

### Workflow for "Cave Entrance in Cliff"
Typical approach:
1. Input cliff mesh (from Gaea or Houdini HeightField)
2. Author a curve along the tunnel axis
3. Sweep a profile along the curve to create cave volume
4. Boolean (Cookie SOP or Boolean SOP) the swept volume out of the cliff mesh
5. Noise-displace the cut surface for natural cave walls
6. Polish with VDB from Polygons -> Convert VDB -> mesh re-surface (gets rid of boolean artefacts)
7. Bake into HDA for reuse

### Export to Blender
Three options:
1. **FBX export** via `File > Export` or FBX render node (loses procedural-ness)
2. **HDA via Houdini Engine for Blender** -- community plugin by Elie Michel using Open Mesh Effect wrapper. Not official. Blender's GPL conflicts with Houdini Engine's proprietary nature so SideFX will not ship a direct integration. Unity / Unreal / Maya / Max have official Houdini Engine support, Blender does not.
3. **USD export** -- Houdini 20 Solaris exports USD, Blender has USD import

### Quality
**AAA / industry standard.** Used on Horizon, God of War, Far Cry, Assassin's Creed, etc.

### Cost
- Apprentice (free, non-commercial, watermark)
- Indie: $269/year (under $100k revenue)
- Core: $1,995 perpetual
- FX: $4,495 perpetual
- Houdini Engine Indie: $199/year

### Python Pipeline
- Python API is first-class in Houdini
- Can orchestrate from outside via `hython` (headless Houdini Python)
- For our Blender addon: would require Houdini installed on the dev machine, `hython` invocation generates FBX, bpy imports it

**Use case for VB:** Overkill for a single cave cut. Would make sense if we build a large library of procedural cave HDAs and want the power of Voronoi/VEX to generate varied systems. Long-term investment, not a quick win.

---

## 5. Substance 3D Modeler

### 3D Cave Support
**Yes.** Substance 3D Modeler is **volumetric** (clay-based) -- truly 3D, not heightmap. You can carve overhangs, caves, recesses naturally like ZBrush.

### Workflow
Same as clay sculpting. Import existing cliff as reference/retopo source, clay sculpt cave entrance, export.

### Export to Blender
FBX, OBJ, GLB, USD. Full mesh export, no procedural parameter exposure.

### Quality
Good but not quite ZBrush-league. More accessible UI, designed for concept/prop sculpting.

### Cost
~$19.99/month Adobe Substance 3D subscription (or included in larger Substance collection).

### Python Pipeline
**No Python API** (Adobe has not opened Modeler's scripting surface). File-based only.

**Use case for VB:** Could be used for manual hero cave asset sculpting, but no automated pipeline hook. Not a fit for our addon.

---

## 6. ZBrush

### 3D Cave Support
**Yes -- this is the gold standard for hero sculpted cave entrances.**

AAA technique (confirmed by Polycount community + Stan Winston School):
1. **DynaMesh** a cube/primitive at 128-256 resolution (blocking)
2. Carve cave entrance with **ClayBuildup / Move / DamStandard / TrimDynamic** brushes
3. **Backface Mask ON** to avoid sculpting through thin walls
4. Redynamesh periodically (every major change) to regenerate topology and prevent stretching
5. ZRemesher for final clean topology (DynaMesh is noisy for detail work)
6. Project details back from DynaMesh onto the ZRemeshed version
7. Export FBX/OBJ for game use

**Community rule:** build caves as *multiple smaller subtools* rather than one giant connected sculpt -- easier to manage.

### Workflow for "Cave Entrance in Cliff"
1. Import MountainPass cliff as reference
2. DynaMesh a cutter volume matching the cliff face area
3. Sculpt cave shape with Move + ClayBuildup
4. Live Boolean subtract from the cliff
5. ZRemesh the result
6. Export

### Export to Blender
FBX, OBJ via GoZ or manual export. No Python pipeline.

### Quality
**AAA. The industry standard** for hero assets. Every Horizon/God of War/Elden Ring cliff you've ever seen went through ZBrush.

### Cost
- Perpetual: $399 (+ upgrade fees)
- Subscription: $39.95/month or $359.91/year
- ZBrushCoreMini: Free (limited)

### Python Pipeline
- ZBrush has **ZScript** (native scripting), not Python. Can automate brush operations.
- No headless mode for automation.
- No way to make this work in our Blender addon automatically.

**Use case for VB:** Manual hero-asset pass by a human artist on the most prominent 3-5 caves in the game. Not for procedural mass generation.

---

## 7. Quixel Megascans / Bridge / Fab

### 3D Cave Support
**Yes -- via photogrammetry.** Many Megascans cliff assets include natural overhangs, nooks, and cave-like recesses because they were scanned from real rock formations that have them.

Notable relevant assets (searchable on Fab):
- **Cave Stone Wall** (`tltncfpg`)
- **Massive Sandstone Cliff** (`vmocdh0`)
- **Layered Rock Cliff** (`tj0leczn`)
- **Sharp Cliff** (`rcygn`)
- **Desert Western Cliff Surface Layered 01** (`vetgagfdy`)

Over 18,000 assets now live on Fab (Epic's merged marketplace).

### Workflow for "Cave Entrance in Cliff"
Two approaches:
1. **Full cliff replacement** -- swap MountainPass cliff section for a Megascans cliff that has the cave built in
2. **Kitbash overlay** -- keep procedural cliff, overlay a Megascans cave-mouth rock piece at the entry point, use vertex blend or boolean to merge

Houdini procedural rock tutorials specifically combine Quixel photoscanned blocks with procedurally scattered geometry for this workflow.

### Export to Blender
- **Quixel Bridge** (legacy) has a Blender plugin for direct import -- dropped by Epic in favor of Fab
- **Fab plugin for Blender** (newer) does the same
- Assets come as FBX + PBR texture set (Albedo, Normal, Roughness, Displacement, AO)

### Quality
**AAA / photoreal.** They are literal photoscans of real rock.

### Cost
- Free with a UE account (Epic's acquisition -- all Megascans assets are free for any use as long as you've accepted the Fab license)
- Historical: paid seat licensing (no longer the model)

### Python Pipeline
- Fab has a REST API for asset discovery
- Blender Fab plugin handles import; can be called from Python via `bpy.ops`
- Assets are files on disk after download, so `bpy.ops.import_scene.fbx()` works

**Use case for VB:** **Strong candidate.** We can download 3-5 canonical cave-mouth rock meshes once, store them in `env_model_library`, and procedurally kitbash them onto cliff faces. This is exactly what AAA studios do.

---

## 8. Procedural Cave Algorithms

### 3D Voronoi Caves
Academic method by Santamaria / Ibirika / Cantero (IEEE 2014): **"Procedural Playable Cave Systems Based on Voronoi Diagram and Delaunay Triangulation."**
- Uses a 2D or 3D cellular automaton to generate a sketch, then builds a Voronoi/Delaunay graph
- Ensures connectivity (playability)
- Parameterized by designer, not black-box

Mark (2015): **"Procedural Generation of 3D Caves for Games on the GPU"** -- full GPU-side voxel cave pipeline, real-time.

L-Systems / schematic maps -- Springer 2016 paper uses turtle graphics for cave corridors.

### Marching Cubes vs Dual Contouring

| Algorithm | Sharp Edges | Triangle Count | Speed | Used By |
|---|---|---|---|---|
| Marching Cubes | No (smooths corners) | Higher | Fast | Minecraft (modified), early voxel games |
| **Dual Contouring** | **Yes** | **Lower** | Fast | **Subnautica, No Man's Sky variants** |
| Dual Marching Cubes | Partial | Medium | Medium | Niche |
| Transvoxel | Yes, w/ LOD | Medium | Fast | LOD-heavy voxel games |

**For caves specifically:** Dual Contouring is the right choice because cave walls have sharp edges where tunnels meet chambers, and it uses the gradient of the SDF to preserve corners that Marching Cubes rounds off.

### Volumetric / SDF Games

| Game | Technique | Notes |
|---|---|---|
| **Dreams (PS4)** | Signed Distance Fields with point-based rendering | Media Molecule's custom renderer, no traditional polys |
| **No Man's Sky** | Voxel terrain + Marching Cubes derivative | Terrain Manipulator lets players carve caves at runtime |
| **Astroneer** | Voxel + flat-shaded polygons, custom solver | Real-time destructible/deformable |
| **Subnautica** | **Dual Contouring** on voxel grid | Entire cave-filled world uses DC |
| **Minecraft** (modern) | Blocky + noise + carvers | 3D Simplex noise now lets them do overhangs + big caves |

Key insight: *every* AAA-or-popular game with real 3D caves uses a **volumetric representation internally** (voxels / SDF), then meshes on demand via Marching Cubes or Dual Contouring.

---

## 9. Blender Native Paths

### Path A: Boolean + Cutter Mesh

**Pipeline (fully bpy-scriptable):**
1. Generate a "cutter" mesh in the shape of the cave interior:
   - Curve bezier along tunnel axis
   - Sweep a noisy profile curve (random radius) along it
   - Convert to mesh, add subsurf + displace (with noise texture) modifiers
   - Apply all modifiers
2. Add **Boolean modifier** (`DIFFERENCE`) on the terrain with `object = cutter`
3. Choose solver:
   - `EXACT` -- handles coplanar faces, slowest, safest
   - `FLOAT` -- fast, no overlap support
   - `MANIFOLD` -- **fastest, manifold-only** (will fail on our 65k-vert non-manifold MountainPass)
4. Apply modifier
5. Remove `cutter` object
6. Clean up: `bpy.ops.mesh.remove_doubles()`, `bpy.ops.mesh.normals_make_consistent()`, optionally `bpy.ops.mesh.fill_holes()`
7. Optional: voxel remesh region around the cut for consistent topology
8. Sculpt mode `Grab` brush for organic wall variation

**Handling non-manifold input:**
The Boolean modifier has a **"Self Intersection"** toggle for non-manifold input -- slower but does work. Alternatively pre-process the terrain mesh through `bpy.ops.mesh.select_non_manifold()` + `bpy.ops.mesh.fill_holes()` to sanitize, then boolean.

Community warning: running booleans in a loop via Python API has historically given unpredictable results (T66593). Prefer one boolean per operation, with `depsgraph.update()` between calls.

### Path B: OpenVDB / SDF Volume

**Pipeline:**
1. Convert terrain mesh to SDF volume: **Geometry Nodes "Mesh to SDF Volume"** node
2. Convert cave cutter to SDF volume same way
3. **Boolean SDF operation** in Geometry Nodes (subtract cutter SDF from terrain SDF)
4. **"Grid to Mesh"** node to re-extract polygons (Marching Cubes under the hood) with threshold 0.0
5. Result is guaranteed manifold and smooth

**Why this is AAA-friendly:**
- Handles non-manifold input gracefully (converts to clean SDF regardless)
- Never produces boolean artifacts (no coplanar-face issues)
- Output topology is uniform (voxel-gridded)
- SDF filters (smoothing, dilation) give us "natural cave wall" look for free
- Native in Blender 4.x / 5.x, no external deps

**Caveat:**
- Output has voxel-ish topology; will need a remesh or decimation pass for game-ready density
- Loses original terrain's high-detail rock surface in the SDF voxelization -- must pick voxel size carefully (small enough to preserve detail, large enough to fit in RAM)
- Blender 5.0+ has full volume grid support in Geometry Nodes, earlier versions are limited

### Path C: Sculpt + Retopo
1. Enter sculpt mode on the terrain
2. Use **Grab** brush with large radius to pull a depression inward
3. **Clay Strips / Draw Sharp** to refine walls
4. **Trim Line / Box Trim** to cut the opening cleanly
5. Remesh + retopo

**Pro:** Artistic control, no manifold issues.
**Con:** Not procedural, not reproducible without recording operator strokes.

### Path D: Blender + Houdini Engine Plugin (Unofficial)
Eli Michel's community branch. Experimental. Not recommended for production.

---

## 10. Recommendation for VeilBreakers MountainPass

**Context recap:** Existing Blender mesh, 65k verts, non-manifold, cliff topology, need a ~10-unit-wide cave entrance at the top of a cliff, fully Python-controllable.

### Primary: Blender Boolean with EXACT solver + self-intersection flag

This is our best path because:
1. **Native bpy** -- no external tools, no file round-trips, no licensing concerns
2. **Existing mesh preserved** -- non-destructive until `Apply`, rock detail on the cliff face is kept
3. **Handles non-manifold** when `self_intersection=True` is set on the modifier
4. **Procedural** -- cutter is a parameterized swept curve, reproducible from a seed
5. **Fast** -- seconds per cave, not minutes

**Implementation sketch:**
```
1. Find entrance point (raycast from cliff normal for an open face)
2. Build bezier tunnel curve (tapered, curved interior, ~10u radius at mouth)
3. Sweep noisy profile along curve -> cutter mesh
4. Add noise displace modifier to cutter
5. Boolean DIFFERENCE on terrain with EXACT solver + self_intersection=True
6. Apply, delete cutter
7. Limited-dissolve + recalc normals on the cut region
8. Optional: vertex paint mask the interior for a "dark cave" shader blend
9. Optional: scatter Megascans cave rock kit pieces at the mouth for hero detail
```

### Fallback: OpenVDB / SDF if boolean fails

If the boolean throws `non-manifold input` errors or produces visibly broken geometry on this specific mesh, pivot to the SDF path -- it is guaranteed to succeed at the cost of some topology regularity.

### Hero-asset pass: Megascans kitbash overlay

For the most visible 3-5 caves in the game, drop a Megascans cave-mouth rock piece at the opening and vertex-blend it into the cut. Photoreal results for free (post-Epic acquisition all Megascans assets are license-free). This is the technique AAA studios actually use -- they don't sculpt every cave from scratch, they carve the opening then hide the seam with a scanned rock piece.

### What NOT to do
- Do not switch to Houdini or ZBrush for procedural mass cave generation -- licensing and external-tool coupling kill the addon's value proposition
- Do not try Gaea / World Creator / World Machine for cave cuts -- they cannot do it, period
- Do not try the Manifold boolean solver -- it will flat-out refuse our non-manifold 65k input
- Do not run booleans in tight Python loops without `depsgraph.update()` -- T66593 shows unpredictable results

### Longer-term roadmap idea
If we later want *large procedural cave networks* (not just entrances), the right move is a **voxel + Dual Contouring** implementation in Geometry Nodes or a custom C extension. This matches Subnautica's approach and is a one-time engineering investment that pays off across every biome.

---

## Sources

### Gaea
- [Terrain Scale - Gaea Documentation](https://docs.quadspinner.com/Guide/Build/Scale.html)
- [Crater Cave-in - Gaea Documentation](https://docs.quadspinner.com/Learning/Techniques/Crater-Cave-In.html)
- [Export Meshes - Gaea Documentation](https://docs.quadspinner.com/Guide/Build/Export-Mesh.html)
- [QuadSpinner Gaea 3.0](https://quadspinner.com/Gaea3)
- [QuadSpinner unveils Gaea 3.0 - CG Channel (Dec 2025)](https://www.cgchannel.com/2025/12/quadspinner-unveils-gaea-3-0/)
- [Mesh Exports - Gaea Documentation](https://docs.gaea.app/using-gaea/build-and-export/mesh-exports)

### World Creator / World Machine
- [World Creator: Digital Terrain Creation Guide](https://www.world-creator.com/en/learn/guides/digital-terrain-creation/digital-terrain-creation.phtml)
- [World Creator: Conventional Export Docs](https://docs.world-creator.com/reference/export/conventional-export)
- [World Machine: Ideas on making caves](https://forum.world-machine.com/t/ideas-on-making-caves/4330)
- [World Machine To Any 3D Rendering Software](https://www.world-machine.com/learn.php?page=workflow&workflow=wf3drender)
- [Getting overhangs on a heightmapped terrain - GameDev.net](https://gamedev.net/forums/topic/250814-getting-overhangs-on-a-heightmapped-terrain/2507350/)
- [Realistic cliffs, caves etc. for terrain - GameDev.net](https://gamedev.net/forums/topic/556744-realistic-cliffs-caves-etc-for-terrain/4576211/)

### Houdini
- [Voronoi Fracture SOP](https://www.sidefx.com/docs/houdini/nodes/sop/voronoifracture-.html)
- [Voronoi Split SOP](https://www.sidefx.com/docs/houdini/nodes/sop/voronoisplit.html)
- [Procedural Generation in Houdini (Kaiyu Bao, WPI)](https://digital.wpi.edu/downloads/j9602501f)
- [Houdini Engine for Blender (community)](https://github.com/eliemichel/HoudiniEngineForBlender)
- [WIP: Houdini Engine for Blender - SideFX Forum](https://www.sidefx.com/forum/topic/74275/)
- [Houdini Procedural Rock - Polycount](https://polycount.com/discussion/208023/houdini-procedural-rock-combined-with-substance-designer)
- [SideFX Project Grot tools (2025)](https://www.cgchannel.com/2025/04/download-free-houdini-tools-from-project-grot/)
- [H19.5 Foundations: Procedural Assets for Unreal](https://www.sidefx.com/tutorials/foundations-procedural-assets-for-unreal/)
- [DoubleJump Academy: Houdini for Games in Unreal](https://www.doublejumpacademy.com/workshops/houdini-for-games-in-unreal-engine)

### ZBrush
- [Sculpting a Cave in Zbrush with Dynamesh - Polycount](https://polycount.com/discussion/184716/sculpting-a-cave-in-zbrush-with-dynamesh-and-mask-outside-shell-cleanly)
- [ZBrush Character Design - Dynamesh - Stan Winston School](https://www.stanwinstonschool.com/tutorials/zbrush-character-design-volume-2-dynamesh-sculpting-techniques)
- [DynaMesh - Maxon Help Center](https://help.maxon.net/zbr/en-us/Content/html/user-guide/3d-modeling/modeling-basics/creating-meshes/dynamesh/dynamesh.html)

### Substance 3D
- [Export models - Substance 3D Modeler](https://helpx.adobe.com/substance-3d-modeler/using/export-models.html)
- [Exporting models - Substance 3D Designer](https://helpx.adobe.com/substance-3d-designer/substance-model-graphs/exporting-models.html)

### Quixel / Megascans
- [Quixel Megascans](https://quixel.com/megascans)
- [Quixel Cave Stone Wall asset](https://quixel.com/megascans/home?assetId=tltncfpg)
- [Quixel Massive Sandstone Cliff](https://quixel.com/megascans/home?assetId=vmocdh0)
- [Quixel Layered Rock Cliff](https://quixel.com/megascans/home?assetId=tj0leczn)

### Volumetric / SDF / Voronoi Caves
- [Procedural Playable Cave Systems (Santamaria et al., IEEE 2014)](https://ieeexplore.ieee.org/document/6980738)
- [Procedural Playable Cave Systems PDF](https://santosgrueiro.com/papers/2014/2014-Santam-Cave.pdf)
- [Procedural Generation of 3D Caves on the GPU (Mark 2015)](http://julian.togelius.com/Mark2015Procedural.pdf)
- [Dual Contouring Tutorial - BorisTheBrave](https://www.boristhebrave.com/2018/04/15/dual-contouring-tutorial/)
- [Voxels and Dual Contouring - dexyfex](https://dexyfex.com/2016/05/16/voxels-and-dual-contouring/)
- [Nick's Voxel Blog - Dual Contouring Chunked Terrain](https://ngildea.blogspot.com/2014/09/dual-contouring-chunked-terrain.html)
- [Procedural World: From Voxels to Polygons](http://procworld.blogspot.com/2010/11/from-voxels-to-polygons.html)
- [Marching Cubes Algorithm - gameidea](https://gameidea.org/2023/12/12/marching-cubes-algorithm/)
- [SDF rendering in Dreams - Beyond3D Forum](https://forum.beyond3d.com/threads/signed-distance-field-rendering-pros-and-cons-as-used-in-ps4-title-dreams-spawn.57006/)
- [No Man's Sky Terrain Manipulator](https://www.nomansskyresources.com/guide-pages/the-terrain-manipulator)

### Blender Native
- [Blender: Mesh Boolean Node](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/mesh/operations/mesh_boolean.html)
- [Blender: Boolean Modifier (Python API)](https://docs.blender.org/api/current/bpy.types.BooleanModifier.html)
- [Blender: Mesh Operators (Python API)](https://docs.blender.org/api/current/bpy.ops.mesh.html)
- [Blender: Volumes Introduction](https://docs.blender.org/manual/en/latest/modeling/volumes/introduction.html)
- [Volume Grids in Geometry Nodes - Blender Developers Blog (Oct 2025)](https://code.blender.org/2025/10/volume-grids-in-geometry-nodes/)
- [Grid to Mesh Node - Blender 5.0 Manual](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/volume/operations/grid_to_mesh.html)
- [GeometryNodeMeshToSDFVolume - Python API](https://docs.blender.org/api/current/bpy.types.GeometryNodeMeshToSDFVolume.html)
- [Bool Tool Extension](https://extensions.blender.org/add-ons/bool-tool/)
- [Terrain Sculptor Blender](https://github.com/blackears/blenderTerrainSculpt)
- [Fixing Non-Manifold Meshes in Blender (Medium)](https://medium.com/@arashtad/fixing-non-manifold-meshes-in-blender-b111b835fbc9)
- [T66593: Boolean Modifier in Python loops](https://developer.blender.org/T66593)
