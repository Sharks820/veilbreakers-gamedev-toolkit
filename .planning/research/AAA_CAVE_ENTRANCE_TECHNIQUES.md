# AAA Cave Entrance Techniques -- Research Dump

**Date:** 2026-04-06
**Purpose:** Replace the current "flat oval with vertex-color gradient" cave entrance (which reads as fake) with real recessed geometry that produces actual shadow occlusion and parallax depth, using techniques proven in AAA pipelines and implementable in Blender via the `bpy`/`bmesh` API.
**Scope:** Techniques only. No code is modified by this document.

---

## TL;DR -- The Decision Tree

When a cave mouth needs to be carved into a procedural terrain cliff, every AAA studio converges on one of four approaches. Pick by context:

1. **Kit-piece + rock dressing (Skyrim / Elden Ring / Witcher 3 exterior dressing).** Keep terrain intact. Drop a pre-modeled, sculpted cave-mouth mesh (manifold, high-detail) at the cliff, then scatter rock meshes ("rock kitbash") around the rim to hide the seam between the kit piece and the terrain. This is the single most robust option for procedural pipelines because it never touches the terrain topology.
2. **Terrain-hole + stitched portal geometry (Witcher 3 REDengine 3).** Mark the tessellation block under the cave mouth as "hole," render that block in a second draw pass with `discard`, and stitch a separately authored cave mouth mesh into the resulting hole. This is what CDPR actually shipped.
3. **Boolean subtract on a solidified terrain patch (Blender-friendly).** Give the terrain thickness with `Solidify`, voxel-remesh it so it is manifold, then `Boolean (Difference)` with an oval cutter. Then sculpt the rim. Works only on a localized terrain patch, not the whole map.
4. **Parallax Occlusion Mapping (POM) with a normal-mapped flat plane.** Cheapest. Good enough from medium distance. Used in Horizon Forbidden West, RDR2, and Unreal Engine 5 for decorative cave pockets the player cannot enter. Fails close-up and fails at steep grazing angles.

**For VeilBreakers' procedural pipeline, the recommended path is #1 (kit piece + rock dressing) as primary and #4 (POM) as fallback for background/unreachable caves.** Approach #3 is the "just make it work in Blender" option when the terrain is small enough to boolean.

---

## 1. AAA Game References

### 1.1 The Witcher 3 (CDPR, REDengine 3)

This is the best-documented AAA cave-in-terrain technique.

**Source:** Marcin Gollent, "Landscape Creation and Rendering in REDengine 3," GDC 2014.
- Paper: [GDC 2014 Gollent Landscape PDF](https://ubm-twvideo01.s3.amazonaws.com/o1/vault/GDC2014/Presentations/Gollent_Marcin_Landscape_Creation_and.pdf)
- GDC Vault: [Landscape Creation and Rendering in REDengine 3](https://www.gdcvault.com/play/1020197/Landscape-Creation-and-Rendering-in)
- Full transcript: [Internet Archive](https://archive.org/stream/GDC2014Gollent/GDC2014-Gollent_djvu.txt)

**How terrain holes work (the actual shipped solution):**

- Terrain resolution: up to 16384² heightmap with vertices spaced at 0.37 m.
- The heightmap terrain alone **cannot** represent cave openings -- it's a 2.5D displaced grid.
- CDPR's explicit requirement was "holes in the terrain itself to include caves."
- Technical constraint: using `discard` in the pixel shader disables early-Z and hi-Z, tanking perf. Index-buffer manipulation is blocked by hardware tessellation.
- **Shipped solution (two-pass terrain rendering):**
  1. During vertical error clipmap updates, mark each tessellation block as "contains a hole" or "does not."
  2. **Pass 1:** Render all non-hole blocks normally (>99% of terrain). Fast path, no discard.
  3. **Pass 2:** Render only the blocks flagged as holes, using `discard` in the pixel shader, and **only at the closest/best clipmap level**. The discard is masked by a low-res hole map.
- The hole is then visually filled by **separately authored cave-mouth mesh assets** (sculpted rock geometry) that stitch into the terrain edge. These kit pieces cover the seam.

**Key takeaway:** Even CDPR does not boolean the terrain. They cut a hole in the heightmap rendering and drop a hand-sculpted rock mesh on top. The terrain hole system is engine-level; the cave mouth is kitbash.

### 1.2 Skyrim / Skyrim Special Edition (Bethesda, Creation Engine)

**Source:** Joel Burgess, "Skyrim's Modular Level Design," GDC 2013.
- Blog with slides: [Joel Burgess blog -- GDC 2013 transcript](http://blog.joelburgess.com/2013/04/skyrims-modular-level-design-gdc-2013.html)
- Game Developer article: [Skyrim's Modular Approach to Level Design](https://www.gamedeveloper.com/design/skyrim-s-modular-approach-to-level-design)
- Community walkthrough: [How to Add Waterfalls, Cave Entrances and Doors, and Map Markers (PDF)](https://skyrimromance.com/wp-content/uploads/2019/12/How_to_Add_Waterfalls_Cave_Entrances_and_Doors_and_Map_Markers.pdf)

**How Skyrim does cave entrances:**

- **Exterior and interior are two separate cells connected by a load door.** The cave entrance you see in the exterior worldspace is **not** the same cave you walk into. It's a cosmetic facade.
- The exterior cave mouth is a **static mesh** (NIF file). Bethesda shipped at minimum:
  - `rockcaveentrance01.nif`
  - `rockcaveentrance02.nif`
  - `dlc01rockcaveentrance01.nif`
  - `glaciercaveentrance02.nif` (ice variant)
  - `caveiswalldoorl01.nif` (connector with embedded door)
  (Source: [Caves HQ Nexus page comments](https://www.nexusmods.com/skyrimspecialedition/mods/22277?tab=posts) -- mod author documenting vanilla mesh filenames.)
- These are **pre-sculpted kit pieces**, not boolean-cut from terrain. The terrain in the Creation Engine is heightmap-based and supports "terrain holes" (quad deletion), but the cave mouth itself is a mesh dropped on top to hide the seam.
- A load door (`LoadDoor`) is embedded inside the cave mouth mesh, triggering a cell transition to the interior worldspace. This is why Skyrim cave entrances almost always go dark immediately past the door -- the interior isn't actually connected to the exterior.
- Rock static meshes and clutter are scattered around the cave mouth to further hide the kit seam where it meets terrain. This is "art fatigue" fighting -- the modular tricks documented in Burgess's talk.

**Key takeaway:** Skyrim cave entrances are **(1) a sculpted rock-mouth NIF + (2) a terrain hole under it + (3) scattered rocks to hide the seam + (4) a load-door trigger for cell transition**. No boolean, no POM.

### 1.3 Red Dead Redemption 2 (Rockstar, RAGE engine)

No public GDC-level paper exists on RDR2's cave technique specifically. From modding community evidence (`Terrain Textures Overhaul`, `Upscaled Terrain` mods on Nexus) and asset teardowns:
- RDR2 caves are overwhelmingly **closed-off backdrops** -- the player cannot enter most of them. They exist as set dressing.
- For the few caves that are enterable (Hidden Tunnel, Elysian Pool, etc.), Rockstar uses **pre-placed sculpted mesh geometry** for the mouth, matching Skyrim's kit-piece approach. The terrain is cut by the mouth mesh's silhouette.
- Decorative unreachable caves use **POM or normal-mapped flat faces** on cliff walls to suggest depth without real geometry.

Sources:
- [Hidden Tunnel -- Red Dead Wiki](https://reddead.fandom.com/wiki/Hidden_Tunnel)
- [Terrain Textures Overhaul (TTO) Nexus mod](https://www.nexusmods.com/reddeadredemption2/mods/2189)

### 1.4 Horizon Zero Dawn / Forbidden West (Guerrilla, Decima)

**Sources:**
- [Guerrilla at GDC 2022](https://www.guerrilla-games.com/read/guerrilla-at-gdc-2022)
- [GPU-Based Procedural Placement in Horizon Zero Dawn](https://www.guerrilla-games.com/read/gpu-based-procedural-placement-in-horizon-zero-dawn)
- [Scaling Tools for Millions of Assets (HFW GDC 2022)](https://www.gdcvault.com/play/1028848/Scaling-Tools-for-Millions-of)

Guerrilla has not published a cave-entrance-specific talk, but Decima's approach is inferred from their procedural placement and asset streaming pipelines:
- HFW has **thousands of decorative cave mouths** in the cliffs of Plainsong and the Forbidden West canyon systems. The vast majority are POM/normal-mapped surface details, not real geometry.
- Reachable caves (tombs, ruins, machine cauldrons) follow the **kit-piece** approach: a sculpted mouth mesh placed on procedurally textured cliff rocks, with Megascans-style photogrammetry rocks scattered around the rim.
- HFW's procedural placement system (evolved from HZD's) lets artists **paint exclusion zones** around cave mouths so vegetation scatter doesn't overlap.

### 1.5 Elden Ring (FromSoftware)

FromSoftware rarely publishes technical talks. From datamining and community reverse-engineering:
- Elden Ring makes an explicit distinction between **Legacy Dungeons** (hand-built interiors connected seamlessly to the overworld -- Stormveil, Leyndell) and **Minor Dungeons** (catacombs/caves/tunnels -- 200+ instanced interiors loaded through a cave-mouth portal). Source: [Elden Ring dungeons guide (PC Gamer)](https://www.pcgamer.com/elden-ring-dungeons-locations-guide/).
- Minor dungeon mouths are **pre-modeled entry portal meshes** dropped on cliff walls. Walking into them triggers a streaming load of a separate interior zone -- identical to Skyrim's pattern.
- The cliff walls behind the mouths are **sculpted rock meshes** (not heightmap terrain) precisely because FromSoft avoids heightmap limitations in tall vertical geometry. The world is stitched from massive sculpted chunks, not displaced from a heightmap.

### 1.6 God of War Ragnarök (Santa Monica Studio)

**Sources:**
- [Santa Monica Studio God of War Ragnarok Art Blast Part 2 (ArtStation)](https://magazine.artstation.com/2023/02/santa-monica-studio-god-of-war-ragnarok-art-blast-part-two/)
- [Creating Buildings & Materials for Asgard (80.lv)](https://80.lv/articles/creating-buildings-materials-for-god-of-war-ragnar-k-s-asgard)
- [How I Studied GoW: Ragnarök for AAA Environment Workflows (The Rookies)](https://discover.therookies.co/2025/09/05/study-god-of-war-ragnarok-to-learn-aaa-environment-workflows/)
- [Patrick Ward -- Jarnsmida Pitmine & Applecore Caves (ArtStation)](https://www.artstation.com/artwork/qQqeyR)

Workflow details that are relevant:
- Environment Artist Jon Arellano's documented workflow: **sculpt rock forms in ZBrush**, use **Create Alpha from Mesh** to generate heightmap alphas, then plug those alphas into **Substance 3D Designer** for tiling cliff/cave material graphs.
- Artist Patrick Ward publicly credited the Svartalfheim caves: he shipped "sculpts, tilers, and materials for Jarnsmida Pitmine and Applecore Caves" -- confirming the caves are hand-sculpted meshes + trim-sheet tiling materials, not boolean cuts from terrain.
- Cave mouths in GoW:R are **triple-layered**: (1) sculpted mouth mesh, (2) decorative rock scatter, (3) POM/trim-sheet detail on the interior surfaces.

---

## 2. Boolean Cut Workflows in Blender

### 2.1 Why `Boolean DIFFERENCE` Fails on Non-Manifold Terrain

A displaced-heightmap terrain is a **single-sided surface** -- it has a top but no bottom, no sides, no volume. Non-manifold. Blender's boolean solvers have specific requirements:

- **FLOAT solver**: Fastest, but the documentation and bug tracker (see [#69150 -- boolean produces non-manifold meshes](https://developer.blender.org/T69150), [#45161 -- Boolean with two manifold objects fails](https://developer.blender.org/T45161)) show it fails silently on open meshes and generates non-manifold output even when inputs are manifold.
- **EXACT solver** (Blender 2.91+): Handles coplanar faces and many edge cases the FLOAT solver chokes on. Still assumes the target has volume.
- **MANIFOLD solver** (Blender 4.2+): Fastest of the three on manifold meshes, but **requires both inputs to be manifold**. Explicitly rejects open surfaces.

**Root cause:** A difference operation is defined as `A - (A ∩ B)`. If `A` has no "inside" (because it has no bottom), then "cutter B intersected with A's volume" is undefined. The boolean may produce a ring of edge loops but no actual removed geometry, or it silently skips.

**Reference error message:** `"Modifier is disabled, skipping apply"` on the Boolean modifier almost always means one of:
1. Object is in Edit Mode (must be Object Mode to apply).
2. Scale/rotation not applied (`Ctrl+A -> Apply Scale/Rotation`).
3. The cutter object reference is missing or points to a deleted object.
4. Modifier visibility toggled off in the stack (camera/viewport icons disabled).

Sources:
- [Blender bug #121705 -- modifier is disabled skipping apply](https://projects.blender.org/blender/blender/issues/121705)
- [Renderosity -- Modifier is disabled skipping apply thread](https://www.renderosity.com/forums/threads/2925871)
- [Artisticrender -- Boolean modifier problems and how to solve them](https://artisticrender.com/boolean-modifier-problems-and-how-to-solve-them/)

### 2.2 Workarounds (in order of robustness)

#### 2.2.1 Solidify BEFORE Boolean (the standard fix)

This is **the** canonical fix for non-manifold terrain booleans.

```
1. Select terrain patch (just the region around the cave, not the whole map).
2. Add Solidify modifier (Thickness = cave depth, e.g. 5 m).
3. Apply Solidify.  -> Terrain now has volume.
4. Add Boolean modifier (Difference, cutter = cave cutter mesh).
5. Apply Boolean.
```

Pitfalls:
- Terrain with steep slopes can get **uneven thickness** from Solidify -- enable `Even Thickness` and `High Quality Normals` in modifier settings.
- Bug T80548 documents "Solidify with Boolean closes the hole" -- mitigation is to apply Solidify first, then run Boolean separately, never stack them.
- Source: [Blender T80548 -- Solidify + Boolean closes hole](https://developer.blender.org/T80548)
- [Artisticrender -- Solidify Modifier guide](https://artisticrender.com/how-to-use-the-solidify-modifier-in-blender/)

#### 2.2.2 Voxel Remesh BEFORE Boolean (the sculpting fix)

The voxel remesher rebuilds the mesh as a watertight volume. Use this when the terrain patch has non-manifold edges, missing faces, or you want to merge multiple cliff meshes into one before cutting.

```python
# Python equivalent
import bpy

# Switch to object mode, select target
bpy.ops.object.mode_set(mode='OBJECT')
bpy.context.view_layer.objects.active = terrain_obj
terrain_obj.select_set(True)

# Set voxel size (smaller = higher resolution; 0.1 m for game terrain)
terrain_obj.data.remesh_voxel_size = 0.1
terrain_obj.data.remesh_voxel_adaptivity = 0.0  # 0 = uniform

# Apply voxel remesh
bpy.ops.object.voxel_remesh()
```

Tradeoffs:
- **Loses UVs** -- voxel remesh does not preserve UV maps. You must re-unwrap or bake UVs via a texture atlas.
- **Loses vertex colors** by default (Blender 3.x can preserve attributes but only if flagged).
- **Quad-less output** -- pure tris. Often fine for terrain.
- **Fills interior holes** -- any hole smaller than the voxel size gets closed.
- Uniform voxel size limits detail fidelity. Adaptive voxels (Blender 3.6+) help but can introduce non-manifold edges near transitions.

Sources:
- [Remesh -- Blender 5.0 Manual](https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/tool_settings/remesh.html)
- [Arashtad -- Fixing Non-Manifold Meshes](https://blog.arashtad.com/3d/blender/fix-non-manifold-meshes-in-blender/)
- [Sinestesia -- What is a non-manifold mesh and how to fix it](https://sinestesia.co/blog/tutorials/non-manifold-meshes-and-how-to-fix-them/)

#### 2.2.3 Mesh > Clean Up > Make Manifold

Lives in `Mesh > Clean Up > Make Manifold` in Edit Mode. Internally runs a loop: select non-manifold (`Ctrl+Shift+Alt+M`), fill holes, recalculate normals, merge by distance -- repeat until no non-manifold verts remain.

**Honest assessment: Make Manifold is brittle on terrain.** It works for small holes (a few missing faces) but on a large displaced heightmap it tends to:
- Create long thin spikes where it tries to bridge large gaps.
- Fail silently on borders that are too large.
- Not create bottom/side faces automatically -- you still need Solidify first to get volume.

Use it as a **post-process cleanup after Solidify** rather than as a primary manifold-conversion strategy. The 3D Print Toolbox addon wraps it with extra checks and is more forgiving.

Sources:
- [Blender T41093 -- Add Make Manifold to Clean Up menu](https://developer.blender.org/T41093)
- [3D Print Toolbox -- Blender Extensions](https://extensions.blender.org/add-ons/print3d-toolbox/)

#### 2.2.4 Knife Project (for flat cuts)

Projects a closed 2D silhouette from one object onto another and cuts the target's faces along that outline. It **does not remove geometry** -- it only creates new edge loops along the projection. You then have to manually `Delete Faces` on the inside.

```
1. Select the terrain as active, shift-select the cutter curve/mesh.
2. Enter Edit Mode on the terrain (with cutter still selected as secondary).
3. Mesh > Knife Project.
4. Delete the faces inside the projected loop.
```

Pros: Works on non-manifold surfaces because it's a 2D projection, not a 3D volume operation. No solver required.
Cons: The cut follows camera projection direction, not surface normals -- angled cliff walls will give you a squashed cut. The resulting hole has no depth; you must extrude the edge loop inward to build the cave tunnel.

Sources:
- [How to use the Knife Project tool correctly](https://www.graphicsandprogramming.net/eng/tutorial/blender/modeling/how-to-use-knife-project-in-blender)
- [Knife Project Tool in Blender guide](https://knifecarehub.com/blog/knife-project-tool-in-blender-a-complete-guide/)

#### 2.2.5 Geometry Nodes Mesh Boolean Node

Introduced in Blender 3.3. Same solver as the modifier, but runs inside a Geometry Nodes tree. Useful for procedural, non-destructive cave generation.

**Performance caveats:**
- Bug T98020 documents **extreme slowdowns** (37 seconds on a simple mesh) when used naively.
- Boolean is computed **once per instance** in a nodes tree -- if you forget to place a `Realize Instances` node before the boolean, it runs N times.
- Self-intersection and hole-tolerance options add significant time. Disable them unless needed.

```
Geometry In -> Realize Instances -> Mesh Boolean (Difference)
                                         ^ cutter
-> Geometry Out
```

Sources:
- [Mesh Boolean Node -- Blender 5.1 Manual](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/mesh/operations/mesh_boolean.html)
- [Blender T98020 -- Extremely Long time delay using geometry nodes boolean](https://developer.blender.org/T98020)
- [Blender Artists -- Boolean Ops in Geometry Nodes any speed tips?](https://blenderartists.org/t/boolean-ops-in-geometry-nodes-any-speed-tips/1460723)

### 2.3 The "Modifier is disabled, skipping apply" error -- full fix checklist

From [Blender #121705](https://projects.blender.org/blender/blender/issues/121705) and community threads:

1. **Ensure Object Mode.** `bpy.ops.object.mode_set(mode='OBJECT')` before applying.
2. **Apply scale and rotation** on both target and cutter. `bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)`.
3. **Check cutter reference is valid.** After any `bpy.ops.object.delete()` or rename, the modifier's `.object` property may point to a dead reference.
4. **Check modifier visibility flags.** `modifier.show_viewport` and `modifier.show_render` must both be `True` when applying.
5. **Check the target is the active object.** `bpy.context.view_layer.objects.active = target_obj`. Applying via operator uses `context.object`, not the selection.
6. **Avoid depsgraph staleness.** After adding a modifier in Python, call `bpy.context.view_layer.update()` before applying.
7. **Use direct modifier application when possible:**
   ```python
   # Safer alternative to bpy.ops.object.modifier_apply
   depsgraph = bpy.context.evaluated_depsgraph_get()
   evaluated_obj = target.evaluated_get(depsgraph)
   new_mesh = bpy.data.meshes.new_from_object(evaluated_obj)
   target.modifiers.clear()
   target.data = new_mesh
   ```
   This pattern avoids the operator's brittle context requirements and is how most production addons apply modifiers.

---

## 3. Sculpting Cave Entrances in Blender

### 3.1 Brush Selection

From [Mesh Sculpt Brush Assets -- Blender 5.1 Manual](https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/brushes/brushes.html) and [Blender Base Camp -- Clay Strips tips](https://www.blenderbasecamp.com/sculpt-with-clay-strips-blender-brush-tips/):

| Brush | Use for | Settings |
|---|---|---|
| **Draw** | Rough pushing of rim inward to form cave mouth | Radius 80%, Strength 0.5, `Ctrl` to invert (push outward) |
| **Clay Strips** | Building up rock lip around the cave rim | Radius 40%, Strength 0.8, hard square falloff |
| **Crease** | Sharp stratification lines in rock walls | Radius 10%, Strength 1.0, `-` (subtract) mode |
| **Inflate** | Bulging rock forms outward near entrance | Radius 60%, Strength 0.4 |
| **Flatten** | Tops of rock lip, erosion planes | Radius 50%, Strength 0.5 |
| **Smooth** (`Shift`) | Cleanup between other brushes | Always available via `Shift` |
| **Scrape** | Angular plane cuts simulating rock fractures | `Area Plane` pinned |

**Workflow for sculpting a cave rim on a boolean-cut terrain:**

1. **Rough the boolean first.** Don't sculpt from zero. Do approach #2.2.1 (Solidify + Boolean) to get a raw hole.
2. **Add Multiresolution modifier** (level 2-4 depending on patch size). See [Multiresolution Modifier -- Blender 5.0 Manual](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/multiresolution.html).
3. **Sculpt at low subdivision first** -- big shapes. Push the rim inward, define the overhang.
4. **Increase subdivision** -- add stratification with Crease brush, erosion divots with Draw Sharp.
5. **Use Draw + Ctrl (invert)** to carve the interior pockets deeper.
6. **Clay Strips on the overhang lip** -- adds the characteristic "chunky rock eyebrow" above cave mouths that reads as AAA quality.
7. **Smooth pass** at highest subdivision to blend transitions.

Sources:
- [Blender Studio -- Basic Sculpting](https://studio.blender.org/training/blender-fundamentals-45-lts/basic-sculpting/)
- [RenderGuide -- Blender Sculpting Tutorial 2024](https://renderguide.com/blender-sculpting-tutorial/)
- [CG Cookie -- Sculpting Rocky Formations](https://cgcookie.com/exercises/exercise-rocky-formations)
- [Blender Artists -- when to use pinch vs crease vs draw sharp](https://blenderartists.org/t/when-to-use-pinch-vs-crease-vs-draw-sharp/1540874)

### 3.2 Multires vs Direct Sculpt

From [Medium -- Remesh + multires workflow](https://medium.com/@skarkkai/remesh-multires-workflow-in-blender-2ae97ae5176d):

- **Multires is the gold standard** for production sculpting. It lets you sculpt hi-res detail while still editing the base cage at low-res. You can bake a displacement/normal map from the hi-res back down for game export.
- **Voxel Remesh (Dyntopo in old versions)** is only for the initial "block-out" phase where topology is changing drastically. Use very large voxel sizes, decrease progressively, then **switch to Multires once topology is locked**.
- **Direct sculpt without Multires** only works if the mesh already has enough subdivisions at the rim -- otherwise the brushes don't have vertices to push. For a post-boolean cave rim, you will have very sparse geometry near the hole and MUST add Multires or subdivide before sculpting.

### 3.3 Mask + Extract for Cave Interiors

Mask Extract is a sculpt-mode tool that turns masked regions into a new object, optionally with Solidify thickness applied automatically. Use it to:

1. **Paint a mask over the cave interior area** (use `M` then paint, or `Box Mask` with `Ctrl+B`).
2. **Sculpt > Mask > Mask Extract** -- creates a new object with just the masked surface, plus optional solidify.
3. Use this extracted surface as the **interior cave wall mesh** -- it already has the curvature of the cliff, so it blends naturally.

This is how several environment artists (including on GoW:R per the ArtStation breakdowns) shell out interior rock geometry from a sculpted cliff without modeling from scratch.

Sources:
- [Mask -- Blender 5.1 Manual](https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/editing/mask.html)
- [BlenderNation -- Sculpting Features & Masks](https://www.blendernation.com/2020/01/15/blender-2-82-new-sculpting-features-masks/)
- [3DSkillUp -- How to Cut a Model in Blender Sculpt Mode](https://3dskillup.art/how-to-cut-a-model-in-blender-sculpt-mode/)

---

## 4. Parallax Occlusion Mapping (POM)

### 4.1 When AAA Games Use POM Instead of Geometry

- **Horizon Forbidden West** (Decima engine): Thousands of decorative cliff caves in the Forbidden West canyons are POM. Digital Foundry analysis confirms that many "cave" surfaces are flat faces with POM from certain angles. Source: [ResetEra -- HFW PC vs PS5 DF analysis](https://www.resetera.com/threads/horizon-forbidden-west-pc-optimised-settings-vs-ps5-digital-foundry.831831/).
- **Red Dead Redemption 2** (RAGE): Background cliff pockets in the Grizzlies and Cumberland Forest use heightmap-driven parallax on flat cliff normals rather than real cave geometry.
- **Unreal Engine 5** ships a **Parallax Occlusion Mapping material function** used by many UE5 games for decorative "cave pockets" on Nanite cliff walls. Source: [Epic Dev Community -- POM tutorial](https://forums.unrealengine.com/t/tutorial-parallax-occlusion-mapping-pom/52527), [ByteTrending -- Mastering POM](https://bytetrending.com/2025/08/25/pom-mastering-parallax-occlusion-mapping-guide-tutorial/).
- **The Witcher 3** uses POM on terrain material layers for pebble/gravel detail, not cave mouths.

**When POM is appropriate:**
- The cave is unreachable (background dressing).
- The player never gets closer than ~10 m.
- The camera angle is generally perpendicular to the cliff, not grazing.
- You can afford the pixel shader cost (POM is cheap on distant LODs, expensive up close).

**When POM breaks:**
- Player walks up to the "cave" -- the fake depth flattens at grazing angles.
- Sky occludes the top of the cave -- POM has no geometry silhouette, the outline stays a flat oval.
- Character shadows fall across it -- shadow projection ignores POM depth.

### 4.2 Implementing POM in Blender Eevee/Cycles

Blender has no native POM node, but several implementations exist:

1. **Parallax Node Extension** (Blender 4.2+): [extensions.blender.org/add-ons/parallax-node/](https://extensions.blender.org/add-ons/parallax-node/). Works in Cycles and EEVEE. Parameters: elevation image, UV map, steps (1-64), strength (0-100), bias (0-2).
2. **mmoeller Parallax Occlusion node** (community fork): [devtalk.blender.org -- Parallax Occlusion Mapping thread](https://devtalk.blender.org/t/parallax-occlusion-mapping/15774). Uses the material displacement output for POM in Eevee.
3. **Anton Neveselov's Parallax Mapping for Blender 2.8** (Gumroad, paid): [neveselov.gumroad.com/l/WhPLq](https://neveselov.gumroad.com/l/WhPLq).
4. **Manual node group**: Bump node driving texture UVs with a Geometry > Incoming vector. Cheap iterative POM that runs in both engines. Implementation pattern:
   ```
   Geometry.Incoming -> Vector > Transform (world->tangent) -> scale by height map
     -> Texture Coordinate UV + offset -> Image Texture
   ```
   Loop 8-32 samples for "steep parallax occlusion."

### 4.3 Real Geometry vs POM -- Tradeoff Table

| Factor | Real Boolean/Sculpted Geometry | Parallax Occlusion Mapping |
|---|---|---|
| Silhouette | Real -- breaks skyline | Fake -- flat oval outline always |
| Shadow casting | Full, correct | Only from normal map, no self-shadow past depth |
| Close-up appearance | Holds up at any distance | Breaks below ~5 m |
| Grazing angles | Correct | Fails visually -- depth flattens |
| GPU cost | Geometry draw + shadow map | 16-64 texture samples per pixel in POM area |
| Memory cost | Vertex buffer (can be large) | 1 height map (~1-4 MB) |
| Authoring cost | High -- sculpt + UV + texture | Low -- just a heightmap |
| Can player enter? | Yes | No |
| Looks AAA? | Yes | Only from specific angles |

---

## 5. Real-World Cave Geometry Sources

### 5.1 Photogrammetry Libraries

- **Quixel Megascans** ([quixel.com/megascans](https://quixel.com/megascans)): The largest commercial photoscan library. Owned by Epic since 2019 -- free for Unreal Engine users. Includes cliff chunks, rock formations, and 3D Assets tagged "cave" / "grotto." As of summer 2024 the Bridge plugin ships ~15k assets. Categories: 3D Assets, 3D Plants, Surfaces, Decals, Imperfections.
- **Polycam** ([polycam.com](https://polycam.com)): Crowd-sourced LiDAR and photogrammetry scans. Many real cave entrance scans captured by hobbyists. License varies per asset.
- **Sketchfab** ([sketchfab.com](https://sketchfab.com)): Mixed paid/free. Search "cave kitbash" for ring-shaped cave tunnel segments.
- **ArtStation Marketplace**: [8K Endless rock cave with ring shape](https://www.artstation.com/marketplace/p/nk09y/8k-endless-rock-cave-with-ring-shape-3d-model-and-materials-kitbash) and similar pre-built cave kitbashes.

### 5.2 Integrating Scanned Cave Assets into Procedural Terrain

Workflow (the one most AAA studios use):

1. **Import the scanned cave mouth** as a single high-res mesh (Megascans ships these as glTF or FBX with Nanite-ready topology).
2. **Place it at the terrain cliff** using your procedural placement system.
3. **Mark a terrain hole** under it -- either:
   - (Unreal) `Terrain > Delete Quads` in the region under the mesh.
   - (Unity) `Terrain.holes` API.
   - (Blender, for pre-export) Boolean subtract a box from the terrain patch under the mesh.
4. **Scatter rock kitbash meshes around the rim** to hide the seam. 6-15 rocks at slightly varying scales is the usual count.
5. **Apply tri-planar or trim-sheet material** to both the terrain and the cave mesh so they blend visually even if the geometry seam is visible.
6. **Place a box/capsule trigger** at the cave mouth for gameplay (level load, lighting change, audio swap).

**Pitfall:** if the scanned mesh has its own bake and the terrain has a different material, you will see a visible "edge" where they meet. The canonical fix is a **blend decal** or a **vertex-color painted transition band** on the rock kitbash meshes at the seam.

Sources:
- [Nanite Virtualized Geometry -- Unreal Engine 5.6 docs](https://dev.epicgames.com/documentation/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
- [Inu Games -- Photogrammetry: making Nanite meshes for UE5](https://inu-games.com/photogrammetry/)
- [Unreal Engine Spotlights -- National Park Service cave photogrammetry](https://www.unrealengine.com/en-US/spotlights/exploring-the-stunning-caves-of-the-national-park-service-in-real-time-3d)

---

## 6. Blender Python API Reference -- Cave Entrance Operations

### 6.1 `bpy.ops.object.modifier_add` -- Creating a Boolean

```python
import bpy

def subtract_cave(target_obj, cutter_obj):
    """Subtract cutter_obj volume from target_obj. Both must be in Object mode."""
    # Ensure target is active and selected
    bpy.ops.object.select_all(action='DESELECT')
    target_obj.select_set(True)
    bpy.context.view_layer.objects.active = target_obj

    # Apply scale/rotation first (critical for boolean reliability)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # Add modifier via direct API (more robust than bpy.ops)
    bool_mod = target_obj.modifiers.new(name="CaveCut", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = cutter_obj
    bool_mod.solver = 'EXACT'  # 'FAST', 'EXACT', or 'MANIFOLD' (4.2+)
    bool_mod.use_self = False
    bool_mod.use_hole_tolerant = True  # tolerates non-manifold input

    # Apply the modifier
    bpy.context.view_layer.update()
    bpy.ops.object.modifier_apply(modifier=bool_mod.name)

    # Hide cutter (keep for re-runs)
    cutter_obj.hide_viewport = True
    cutter_obj.hide_render = True
```

Sources:
- [BooleanModifier -- Blender Python API](https://docs.blender.org/api/current/bpy.types.BooleanModifier.html)
- [Object Operators -- Blender Python API](https://docs.blender.org/api/current/bpy.ops.object.html)
- [Gist -- Blender Python boolean union](https://gist.github.com/openroomxyz/f790b1037cd2ffdf6b936e906d232a78)

### 6.2 `bmesh.ops.boolean` -- Low-Level Boolean

```python
import bpy, bmesh

def bmesh_boolean_difference(target_obj, cutter_obj):
    """Boolean via bmesh -- useful when you need to chain multiple ops in one pass."""
    bm = bmesh.new()
    bm.from_mesh(target_obj.data)

    # Add cutter geometry into the same bmesh, tagged with a layer
    cutter_bm = bmesh.new()
    cutter_bm.from_mesh(cutter_obj.data)
    cutter_geom = bmesh.ops.duplicate(cutter_bm, geom=list(cutter_bm.verts) + list(cutter_bm.edges) + list(cutter_bm.faces))
    # Transform cutter into target's local space
    # ... (omitted: matrix transform)

    # Note: bmesh.ops.boolean was removed in later Blender versions.
    # Modern Blender uses bpy.ops.mesh.intersect_boolean for the mesh-level boolean
    # from within Edit Mode, or the modifier API above.
    # See: https://docs.blender.org/api/current/bmesh.ops.html

    bm.to_mesh(target_obj.data)
    bm.free()
    cutter_bm.free()
```

**Important:** `bmesh.ops.boolean` historically existed but has been deprecated/removed in favor of the modifier API and `bpy.ops.mesh.intersect_boolean` (edit-mode operator). For procedural pipelines, **use the modifier API** (section 6.1) as the canonical approach.

Sources:
- [BMesh Operators (bmesh.ops) -- Blender Python API](https://docs.blender.org/api/current/bmesh.ops.html)
- [BMesh Module -- Blender Python API](https://docs.blender.org/api/current/bmesh.html)

### 6.3 Voxel Remesh via Python

```python
import bpy

def voxel_remesh(obj, voxel_size=0.1):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode='OBJECT')

    obj.data.remesh_voxel_size = voxel_size
    obj.data.remesh_voxel_adaptivity = 0.0
    obj.data.use_remesh_smooth_normals = True
    obj.data.use_remesh_preserve_volume = True
    obj.data.use_remesh_preserve_paint_mask = False
    obj.data.use_remesh_preserve_sculpt_face_sets = False

    bpy.ops.object.voxel_remesh()
```

### 6.4 Solidify Before Boolean (Python)

```python
import bpy

def add_solidify(obj, thickness=5.0):
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="TerrainThickness", type='SOLIDIFY')
    mod.thickness = thickness
    mod.offset = -1.0  # extrude downward
    mod.use_even_offset = True       # "Even Thickness"
    mod.use_quality_normals = True   # "High Quality Normals"
    bpy.ops.object.modifier_apply(modifier=mod.name)
```

### 6.5 Knife Project via Python

Knife Project is only exposed via `bpy.ops.mesh.knife_project` and requires Edit Mode with a specific selection state:

```python
import bpy

def knife_project_cut(target_obj, cutter_obj):
    # Select both, target active, enter edit mode on target with cutter also selected
    bpy.ops.object.select_all(action='DESELECT')
    cutter_obj.select_set(True)
    target_obj.select_set(True)
    bpy.context.view_layer.objects.active = target_obj
    bpy.ops.object.mode_set(mode='EDIT')
    # Align view so projection direction matches desired cut direction
    bpy.ops.mesh.knife_project(cut_through=True)
    bpy.ops.object.mode_set(mode='OBJECT')
```

The `cut_through=True` flag ensures the cut goes all the way through the mesh (not just the front face).

### 6.6 Sculpt Mode + Multires via Python

```python
import bpy

def add_multires_and_sculpt(obj, levels=3):
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="Multires", type='MULTIRES')
    # Subdivide N times
    for _ in range(levels):
        bpy.ops.object.multires_subdivide(modifier=mod.name, mode='CATMULL_CLARK')
    # Enter sculpt mode
    bpy.ops.object.mode_set(mode='SCULPT')
```

### 6.7 Robust Modifier Apply (Bypass the Operator)

This is the production-grade pattern that avoids the `"modifier is disabled, skipping apply"` errors:

```python
import bpy

def apply_all_modifiers_safe(obj):
    """Evaluate the modifier stack into a new mesh, bypassing operator context issues."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated_obj = obj.evaluated_get(depsgraph)
    new_mesh = bpy.data.meshes.new_from_object(evaluated_obj)
    old_mesh = obj.data
    obj.modifiers.clear()
    obj.data = new_mesh
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
```

This is the pattern used by Blender's own addons (Asset Manager, 3D Print Toolbox) when they need to guarantee a modifier stack applies correctly regardless of the calling context.

---

## 7. Recommended Implementation Path for VeilBreakers

Given the current state (flat oval + vertex gradient = fake), here is the prioritized fix order:

### Phase A -- Quick Win (hours)
Replace the flat oval with a **POM material** on a slightly indented mesh (not flat). Use the Parallax Node extension or a bump-driven UV offset. This alone removes the "oval decal" read at medium distance. Cost: one material, no geometry changes.

### Phase B -- Real Geometry (days)
1. For each cave location in the procedural pipeline, generate a **local terrain patch** (10-20 m radius around the cave point) as a separate mesh.
2. Run **Solidify (5 m thickness, offset -1, even thickness) -> apply**.
3. Generate an **oval/elliptical cutter** mesh (sized to cave opening + 2 m safety).
4. Run **Boolean DIFFERENCE with EXACT solver + use_hole_tolerant -> apply** via the robust modifier apply pattern (section 6.7).
5. Add **Multires (level 2)** and sculpt the rim with the brush workflow in section 3.1. (Or skip if you want it automated -- just run a few noise displacement passes via geometry nodes.)
6. Rejoin the patch to the main terrain via **Boolean UNION** or simple vertex merge at the shared edge.

### Phase C -- Kit Dressing (days)
1. Pull **6-15 rock kitbash meshes** from your existing rock library (or generate via `blender_quality` rock generator).
2. Scatter them around the cave rim with randomized scale/rotation using a **Particle System with Object mode** or manual placement via Python.
3. Place 2-3 **overhang rocks** above the cave mouth -- this is the key AAA touch that sells depth.

### Phase D -- Visual Verification
Use `blender_viewport action=contact_sheet` from multiple angles (especially 20-degree grazing angles, which is where the old oval failed hardest). Compare against reference AAA screenshots.

---

## 8. Key Insights From Research

1. **No AAA studio booleans the main terrain.** They either (a) mark a terrain hole at the engine level and drop a kit piece, or (b) use POM, or (c) sculpt the entire cliff as a separate mesh from the start. Trying to boolean a full game terrain is fighting the wrong battle.
2. **The "kit piece + rock dressing" pattern is universal.** Skyrim, Witcher 3, Elden Ring, GoW:R all do it. The rocks hiding the seam are as important as the cave mouth mesh itself.
3. **POM is not cheating -- it's the standard technique for unreachable caves.** Don't dismiss it for background dressing.
4. **Solidify + Boolean is the correct Blender pattern** for a local terrain patch. The full terrain is the wrong scope -- cut a patch, boolean it, stitch back.
5. **Multires is the sculpting gold standard.** Voxel remesh is only the pre-stage. Don't sculpt on raw boolean output without adding subdivision levels first.
6. **The "modifier is disabled, skipping apply" error is almost always a context/state bug, not a data bug.** Use the depsgraph + new_from_object pattern in section 6.7 to avoid it entirely.
7. **The rim sculpt is what makes it look AAA.** Even a perfect boolean produces a "cookie cutter" result. The overhang lip (Clay Strips) and stratification (Crease) on the rim is what reads as "carved by nature."

---

## Sources (Consolidated)

### AAA Game Technical References
- [GDC 2014 -- Landscape Creation and Rendering in REDengine 3 (PDF)](https://ubm-twvideo01.s3.amazonaws.com/o1/vault/GDC2014/Presentations/Gollent_Marcin_Landscape_Creation_and.pdf)
- [GDC Vault -- Landscape Creation and Rendering in REDengine 3](https://www.gdcvault.com/play/1020197/Landscape-Creation-and-Rendering-in)
- [Internet Archive -- GDC 2014 Gollent full text](https://archive.org/stream/GDC2014Gollent/GDC2014-Gollent_djvu.txt)
- [Joel Burgess -- Skyrim's Modular Level Design GDC 2013 transcript](http://blog.joelburgess.com/2013/04/skyrims-modular-level-design-gdc-2013.html)
- [Game Developer -- Skyrim's Modular Approach to Level Design](https://www.gamedeveloper.com/design/skyrim-s-modular-approach-to-level-design)
- [80.lv -- Building Huge Open Worlds: Modularity, Kits & Art Fatigue](https://80.lv/articles/building-huge-open-worlds-modularity-kits-art-fatigue)
- [Guerrilla Games -- GDC 2022](https://www.guerrilla-games.com/read/guerrilla-at-gdc-2022)
- [Guerrilla Games -- GPU-Based Procedural Placement in HZD](https://www.guerrilla-games.com/read/gpu-based-procedural-placement-in-horizon-zero-dawn)
- [GDC Vault -- Scaling Tools for Millions of Assets for HFW](https://www.gdcvault.com/play/1028848/Scaling-Tools-for-Millions-of)
- [ArtStation Magazine -- GoW Ragnarok Art Blast Part 2](https://magazine.artstation.com/2023/02/santa-monica-studio-god-of-war-ragnarok-art-blast-part-two/)
- [80.lv -- Creating Buildings & Materials for GoW Ragnarok's Asgard](https://80.lv/articles/creating-buildings-materials-for-god-of-war-ragnar-k-s-asgard)
- [The Rookies -- How I Studied GoW:R for AAA Environment Workflows](https://discover.therookies.co/2025/09/05/study-god-of-war-ragnarok-to-learn-aaa-environment-workflows/)
- [Patrick Ward -- GoW Ragnarok Svartalfheim Caves (ArtStation)](https://www.artstation.com/artwork/qQqeyR)
- [PC Gamer -- Elden Ring dungeons locations guide](https://www.pcgamer.com/elden-ring-dungeons-locations-guide/)

### Blender Boolean and Mesh Cleanup
- [Blender Manual -- Boolean Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/booleans.html)
- [Blender Manual -- Mesh Boolean Node (Geometry Nodes)](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/mesh/operations/mesh_boolean.html)
- [Blender T69150 -- boolean produces non-manifold output](https://developer.blender.org/T69150)
- [Blender T45161 -- Boolean doesn't work with two manifold similar objects](https://developer.blender.org/T45161)
- [Blender T80548 -- Solidify with Boolean closes the hole](https://developer.blender.org/T80548)
- [Blender T98020 -- geometry nodes boolean extreme slowdown](https://developer.blender.org/T98020)
- [Blender T41093 -- Add Make Manifold to Clean Up menu](https://developer.blender.org/T41093)
- [Blender Projects #121705 -- modifier is disabled skipping apply](https://projects.blender.org/blender/blender/issues/121705)
- [Blender Developer Forum -- Manifold Boolean feedback](https://devtalk.blender.org/t/manifold-boolean-feedback/40150)
- [Artisticrender -- Boolean modifier problems and how to solve them](https://artisticrender.com/boolean-modifier-problems-and-how-to-solve-them/)
- [Artisticrender -- Solidify Modifier guide](https://artisticrender.com/how-to-use-the-solidify-modifier-in-blender/)
- [Artisticrender -- How to repair a mesh in Blender](https://artisticrender.com/how-to-repair-a-mesh-in-blender/)
- [Hard Ops -- Boolean Tips](https://hardops-manual.readthedocs.io/en/latest/boolean_beginner_tips/)
- [Blender Artists -- Boolean Union modifier on manifold object produces non-manifold](https://blenderartists.org/t/boolean-union-modifier-on-manifold-object-produces-non-manifold-object/700896)
- [Blender Artists -- Boolean Ops in Geometry Nodes speed tips](https://blenderartists.org/t/boolean-ops-in-geometry-nodes-any-speed-tips/1460723)
- [Medium -- Fixing Non-Manifold Meshes in Blender (Arashtad)](https://medium.com/@arashtad/fixing-non-manifold-meshes-in-blender-b111b835fbc9)
- [Sinestesia -- Non-manifold meshes and how to fix them](https://sinestesia.co/blog/tutorials/non-manifold-meshes-and-how-to-fix-them/)
- [Eva Herbst -- Blender remeshing guide (GitHub)](https://github.com/evaherbst/Blender_remeshing_guide)

### Sculpting in Blender
- [Blender Manual -- Mesh Sculpt Brush Assets](https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/brushes/brushes.html)
- [Blender Manual -- Multiresolution Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/multiresolution.html)
- [Blender Manual -- Mask (Sculpt Mode)](https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/editing/mask.html)
- [Blender Manual -- Remesh (Voxel)](https://docs.blender.org/manual/en/latest/sculpt_paint/sculpting/tool_settings/remesh.html)
- [Blender Studio -- Basic Sculpting Fundamentals 4.5 LTS](https://studio.blender.org/training/blender-fundamentals-45-lts/basic-sculpting/)
- [Blender Base Camp -- Sculpt with Clay Strips tips](https://www.blenderbasecamp.com/sculpt-with-clay-strips-blender-brush-tips/)
- [RenderGuide -- Blender Sculpting Tutorial 2024](https://renderguide.com/blender-sculpting-tutorial/)
- [CG Cookie -- Sculpting Rocky Formations](https://cgcookie.com/exercises/exercise-rocky-formations)
- [Lesterbanks -- Getting Started With MultiRes Sculpting](https://lesterbanks.com/2020/09/getting-started-with-multires-sculpting-in-blender/)
- [Medium -- Remesh + multires workflow in Blender](https://medium.com/@skarkkai/remesh-multires-workflow-in-blender-2ae97ae5176d)
- [BlenderNation -- Sculpting Features & Masks](https://www.blendernation.com/2020/01/15/blender-2-82-new-sculpting-features-masks/)

### Parallax Occlusion Mapping
- [Unity Shader Graph -- Parallax Occlusion Mapping Node 17.2](https://docs.unity3d.com/Packages/com.unity.shadergraph@17.2/manual/Parallax-Occlusion-Mapping-Node.html)
- [Epic Dev Community -- POM tutorial](https://forums.unrealengine.com/t/tutorial-parallax-occlusion-mapping-pom/52527)
- [Epic Dev Community -- Creation of POM in Details](https://dev.epicgames.com/community/learning/tutorials/kyXK/unreal-engine-creation-of-parallax-occlusion-mapping-pom-in-details)
- [ByteTrending -- POM Mastering Parallax Occlusion Mapping](https://bytetrending.com/2025/08/25/pom-mastering-parallax-occlusion-mapping-guide-tutorial/)
- [Harry Alisavakis -- My take on shaders: Parallax effect Part I](https://halisavakis.com/my-take-on-shaders-parallax-effect-part-i/)
- [Fox Render Farm -- Learn Parallax Mapping](https://www.foxrenderfarm.com/share/learn-parallax-mapping/)
- [LlamaCademy -- POM Depth Illusion in Shader Graph](https://llamacademy.dev/tutorials/8tfqQ829bIQ/)
- [Oregon State -- Practical POM PDF](https://web.engr.oregonstate.edu/~mjb/cs519/Projects/Papers/Parallax_Occlusion_Mapping.pdf)
- [Blender Developer Forum -- Parallax Occlusion Mapping thread](https://devtalk.blender.org/t/parallax-occlusion-mapping/15774)
- [Blender Artists -- Parallax Occlusion Node Development (Fake Displacement in Eevee)](https://blenderartists.org/t/parallax-occlusion-node-development-fake-displacement-in-eevee/1266999)
- [Blender Extensions -- Parallax Node add-on](https://extensions.blender.org/add-ons/parallax-node/)
- [Blender T68477 -- Parallax Occlusion Mapping](https://developer.blender.org/T68477)
- [Neveselov -- Parallax Mapping for Blender 2.8](https://neveselov.gumroad.com/l/WhPLq)

### Photogrammetry & Asset Integration
- [Quixel Megascans](https://quixel.com/megascans)
- [Quixel Megascans License](https://quixel.com/en-US/license)
- [Nanite Virtualized Geometry -- Unreal Engine 5.6 docs](https://dev.epicgames.com/documentation/unreal-engine/nanite-virtualized-geometry-in-unreal-engine)
- [Epic Dev Community -- Mastering Megascans path](https://dev.epicgames.com/community/learning/paths/yzG/unreal-engine-realityscan-mastering-megascans-a-guide-to-photogrammetry-and-asset-creation)
- [Inu Games -- Photogrammetry making Nanite meshes for UE5](https://inu-games.com/photogrammetry/)
- [Unreal Engine Spotlights -- NPS cave photogrammetry](https://www.unrealengine.com/en-US/spotlights/exploring-the-stunning-caves-of-the-national-park-service-in-real-time-3d)
- [ArtStation Marketplace -- 8K Endless rock cave kitbash](https://www.artstation.com/marketplace/p/nk09y/8k-endless-rock-cave-with-ring-shape-3d-model-and-materials-kitbash)

### Blender Python API
- [Blender Python API -- bpy.types.BooleanModifier](https://docs.blender.org/api/current/bpy.types.BooleanModifier.html)
- [Blender Python API -- bpy.ops.object](https://docs.blender.org/api/current/bpy.ops.object.html)
- [Blender Python API -- bmesh module](https://docs.blender.org/api/current/bmesh.html)
- [Blender Python API -- bmesh.ops](https://docs.blender.org/api/current/bmesh.ops.html)
- [Gist -- Blender Python boolean union example](https://gist.github.com/openroomxyz/f790b1037cd2ffdf6b936e906d232a78)

### Skyrim Modding References
- [Joel Burgess GDC 2013 talk transcript](http://blog.joelburgess.com/2013/04/skyrims-modular-level-design-gdc-2013.html)
- [Caves HQ Nexus mod (vanilla mesh filenames)](https://www.nexusmods.com/skyrimspecialedition/mods/22277?tab=posts)
- [Immersive Cave Entrances at Skyrim SE Nexus](https://www.nexusmods.com/skyrimspecialedition/mods/29220)
- [Skyrim Romance PDF -- Adding Waterfalls, Cave Entrances and Doors](https://skyrimromance.com/wp-content/uploads/2019/12/How_to_Add_Waterfalls_Cave_Entrances_and_Doors_and_Map_Markers.pdf)
- [ELFX Cave Cliff Mesh Fix](https://www.nexusmods.com/skyrimspecialedition/mods/67918)
- [Static Mesh Improvement Mod (SMIM)](https://www.nexusmods.com/skyrim/mods/8655)
