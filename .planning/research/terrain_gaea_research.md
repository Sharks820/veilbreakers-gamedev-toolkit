# Quadspinner Gaea Terrain Generation - Deep Research

**Researched:** 2026-04-02
**Domain:** Procedural terrain generation, erosion simulation, geological accuracy
**Confidence:** HIGH (primary sources: official Gaea documentation, QuadSpinner blog, Gaea 2/3 release notes)

## Summary

Quadspinner Gaea is the industry-leading procedural terrain generation tool used in AAA games and VFX. Its core differentiator is **physically-based erosion simulation** combined with a **node graph architecture** that allows composing complex geological formations from simple primitives. Gaea's terrain looks photorealistic because it simulates multiple erosion types (hydraulic, thermal, fluvial, glacial, coastal, aeolian) in multiple passes, uses resolution-independent algorithms, and maps materials to terrain features using physical data maps (slope, curvature, flow, altitude) rather than simple noise.

The key principles we can replicate in our Blender pipeline are: (1) multi-pass erosion with different parameters per pass, (2) data-driven texturing using slope/altitude/curvature/flow masks, (3) LookDev surface detailing that adds complexity without altering primary shape, and (4) layered material composition using satellite-derived color gradients.

**Primary recommendation:** Implement a multi-pass erosion system in our Blender terrain generators that chains hydraulic erosion (primary carving), thermal erosion (talus/debris), and surface detailing (stratification, fractures) -- then drive material assignment from computed slope, altitude, curvature, and flow data maps.

---

## 1. Core Erosion Algorithms

### Hydraulic Erosion (Primary)

Gaea's primary erosion system. Two implementations exist:

**Erosion (Classic / Erosion_1)**
- Simulates water flowing over terrain, dissolving and transporting sediment
- Key parameters:
  - **Duration** (default 4%): How long the simulation runs. Higher = more erosion but diminishing returns past ~30%
  - **Rock Softness**: How easily material erodes. Softer rock erodes faster
  - **Strength**: Sediment transport capacity -- how much dissolved mineral water carries
  - **Downcutting**: Vertical erosion allowing water to transport undissolved materials, creating deeper gullies
  - **Inhibition**: Restrains downcutting by determining how dropped sediments slow material movement
  - **Base Level**: Lowest elevation where downcutting stops and deposition begins
  - **Feature Scale**: Controls lateral size of largest erosion features (width of valleys/ridges) -- the primary artistic control
  - **Volume**: Treats water flows volumetrically, increasing water levels and creating wider channels
  - **Sediment Removal**: Removes erosion-generated deposits
  - **Random Sedimentation**: Randomizes deposition patterns for non-uniform results
- Outputs three data maps: **Wear** (where material was removed), **Deposits** (where sediment settled), **Flow** (sediment transport paths)
- Resolution-independent: 512x512 preview maintains essential parity with 4K/8K builds
- Deterministic mode available (single-core, slower but reproducible)
- Aggressive mode for faster processing with minor quality tradeoffs

**Erosion_2 (Gaea 2.0+, GPU-accelerated)**
- Runs entirely on GPU for massive performance gains
- Adds **orographic rainfall** simulation:
  - Directional precipitation (rain falls more intensely from one direction)
  - Rain shadow controls (terrain blocks rainfall from certain directions)
  - Altitude limits for rainfall effects
  - Slope limits for precipitation zones
- Selective precipitation by mask, slope, or altitude
- Enables accurate microclimate simulation
- Same core outputs (Wear, Deposits, Flow) plus enhanced sediment transport

### Thermal Erosion

Sister process to hydraulic erosion. Simulates mechanical weathering from temperature changes.

- **Duration**: How long thermal process runs
- **Strength**: Intensity of thermal erosion effect
- **Anisotropy**: Controls how rock is affected and deposits formed. Low values preserve terrain features; high values create pronounced talus but heavily erode sharp peaks
- **Talus Angle**: Slope angle of sediment deposits (critical for realistic scree/debris)
- **Talus Settling**: How sediments stabilize within talus piles
- **Sediment Removal**: Amount of material stripped away
- **Fine Detail**: Enables rocky debris within talus deposits
- **Debris Size**: Scale of debris when Fine Detail is enabled
- Smooths terrain while eroding -- natural complement to hydraulic which carves

### Fluvial Erosion

"Secondary" erosion best applied on already-eroded surfaces. Carving takes priority over sedimentation.

- **Duration**: Simulation cycles (200 typically sufficient)
- **Power**: Erosion strength
- **Granularity**: Debris characteristics (fine dust to coarse boulders)
- **BasLen**: Sub-simulation length per particle
- **Radius**: Area of effect per particle
- Uses parallel processing (can produce grid artifacts)
- Best for adding light erosion where carved channels matter more than deposits

### Breaker (Crack/Ravine Formation)

Creates large cracks following hydraulic erosion rules but **without soil deposits**.

- **Duration**: Number of breakage iterations
- **River Length**: Maximum extent for each break/river formation
- **Erosion Power**: Intensity of breakage. Higher = sharper discontinuities
- **Depth**: How deep cracks penetrate
- **Hard Cracks**: Removes antialiasing/smoothing for sharper edges
- **Mode**: Fast (variable patterns) vs Accurate (consistent patterns)

### Upcoming in Gaea 3.0 (mid-2026)

- **Sand Simulation**: High-performance aeolian solver -- subtle surface drift to kilometer-scale dunes driven by realistic wind physics
- **Next-Gen Thermal**: More natural patterns, sharper feature preservation, improved sediment transport
- **Advanced Snow Simulation**: New physics engine for snow tools
- **Rivers**: Combined user guidance with natural meander generation

---

## 2. Node Graph Architecture

### How the Graph Works

Gaea uses a **directed acyclic graph (DAG)** of nodes. Data flows from left to right:

```
[Primitive/Generator] --> [Modify/Combine] --> [Erosion] --> [Surface/LookDev] --> [Color/Export]
```

- Each node takes heightfield inputs and produces heightfield + data map outputs
- Nodes can be chained in any order (though pipeline order matters for realism)
- Any node can be marked for export (F3 or right-click > Mark for Export)
- Preview at any resolution; final build at target resolution
- Mutations system generates up to 99 terrain variations from one graph via seed changes

### Node Categories

**Primitives (Generators)**
| Node | Purpose |
|------|---------|
| Perlin | Classic Perlin noise heightfield |
| Voronoi | Voronoi cell-based terrain (plateaus, cracked earth) |
| SlopeNoise | Expansive sloping terrains with internal noise distortions, ideal for erosion |
| MultiFractal | Multi-octave fractal noise |
| Noise | General-purpose noise generator |
| Cellular / Cellular3D | Cell-based patterns |
| Gabor | Gabor noise (directional/anisotropic) |
| CutNoise | Cut/carved noise patterns |
| DotNoise | Dot-based noise |
| DriftNoise | Drifting noise patterns |
| LineNoise | Linear noise patterns |
| Cracks | Crack pattern generator |
| Pattern | Geometric patterns |
| WaveShine | Wave-based heightfields |
| Shape | Basic geometric shapes |
| Cone / Hemisphere | Geometric primitives |
| Gradient (Linear/Radial) | Gradient ramps |
| File / Resource | Import external heightmaps |
| Draw | Hand-painted input |

**Terrain (Geological Generators)**
| Node | Purpose |
|------|---------|
| Mountain | Single mountain with realistic profile |
| MountainRange | Mountain chain generation |
| MountainSide | Mountain slope/face |
| Ridge | Ridge/spine formation |
| Canyon | Canyon geological structure |
| Crater / CraterField | Impact crater(s) |
| DuneSea | Sand dune fields |
| Island | Island with shore/beach |
| Plates | Tectonic plate formations |
| Rugged | Rugged rocky terrain |
| Slump | Landslide/slump formations |
| Uplift | Tectonic uplift shapes |
| Volcano | Volcanic cone with caldera |
| Badlands | Badlands erosion patterns |

**Erosion / Simulation**
| Node | Purpose |
|------|---------|
| Erosion (Classic) | Full-control hydraulic erosion |
| Erosion_2 | GPU-accelerated hydraulic erosion with orographic rainfall |
| Wizard | Simplified erosion with built-in recipes |
| Thermal | Thermal weathering and talus deposits |
| Fluvial | Secondary carving-focused erosion |
| Breaker | Crack/ravine formation without deposits |
| Stratify | Broken strata / rock layers in non-linear fashion |
| Sediment | Thick sedimentation layer (sand, snow, generic) with Drift mode for glaciers |
| Alluvium | Soil deposits for filling crevices or covering features |
| Hydro | Waterflow erosion (rivers, ancient seabeds). Lateral + Ventral modes |

**LookDev (Composite Surface Detail)**
| Node | Purpose |
|------|---------|
| Anastomosis | Interconnected water-carved structures |
| Canyonizer | Canyon networks; at low yield adds semi-superficial detail |
| Carver (formerly Landform) | Terrain carving/shaping |
| Fold | Geological folding |
| Shatter | Surface impact breakage patterns |
| Shear | Shearing deformation |
| Stacks | Stratified mesa formations with realistic layering |

**Data Maps (Masks/Analysis)**
| Node | Purpose |
|------|---------|
| Height | Altitude-based mask |
| Slope | Slope angle mask (isolate cliffs, gentle hills) |
| Curvature | Surface curvature mask (convex/concave) |
| Flow | Simulated rainfall/water accumulation paths |
| Velocity | Water flow speed mask |
| Soil | Organic soil distribution mask |
| Texture / SurfTex | Quick pseudo-random texturing masks |

**Color / Texturing**
| Node | Purpose |
|------|---------|
| CLUTer | Color lookup table mapped to height (gradient-to-elevation) |
| SatMaps | 1400+ satellite-derived color gradients for realistic coloration |
| Synth | Synthesized color gradients |
| Combine | Blend/composite multiple color layers |
| Biome | Fresh water-based ecosystem coloring |

**Snow/Ice (Gaea 2.2+)**
| Node | Purpose |
|------|---------|
| Snow | Snow accumulation based on slope/curvature |
| Snowfield | Large snow coverage areas |
| Glacier | Glacial ice formations |
| Dusting | Light snow/frost dusting |
| Icefloe | Ice floe patterns |

**Other Simulations**
| Node | Purpose |
|------|---------|
| Water/Coast | Lake, river, coastal simulation with advanced hydrology |
| Debris | Physics-based rock fragment generation (millions of pieces) |
| Vegetation/Trees | Procedural plant distribution based on terrain/hydrology/climate |
| Global Accumulator | Consolidates masks from Snow, Water, Debris, Tree sims |

---

## 3. What Makes Gaea Terrain Look Natural vs Procedural

### Multi-Pass Erosion (The Single Most Important Technique)

Gaea terrains look natural because artists chain **multiple erosion passes with different parameters**:

1. **Pass 1 -- Structural**: High Duration (30%), Selective Processing set to Altitude bias. Creates initial large-scale flow structure on mountain tops.
2. **Pass 2 -- Carving**: 100% Downcutting, Base Level adjusted. Creates strong flow structures and deep channels everywhere.
3. **Pass 3 -- Homogenizing**: Default settings. Smooths and blends the texture while preserving larger carved features.

Each pass adds another "generation" of geological history. Single-pass erosion looks CG; multi-pass looks like real geology.

### Resolution Independence

The erosion algorithm preserves features across resolutions. A 512x512 preview maintains essential parity with 4K/8K builds. This means the algorithm operates on **relative feature scale**, not pixel count -- critical for avoiding resolution-dependent artifacts.

### Selective Processing (Mask-Driven Erosion)

Erosion is not applied uniformly. Masks control:
- **Rock Softness** per region (harder rock resists, creating ridges)
- **Erosion Strength** per region (sheltered areas erode less)
- **Precipitation Amount** per region (rain shadow, microclimate simulation)

This creates the **heterogeneous erosion** seen in real landscapes where different rock types and exposure levels produce wildly different erosion patterns in the same terrain.

### LookDev Surface Detail

LookDev nodes add **high-frequency geological detail** without altering the primary terrain shape:
- Stratification (rock layers)
- Fracture patterns
- Anastomosis (braided channel networks)
- Canyon micro-detail

These are applied at low strength to add visual complexity that erosion alone cannot produce.

### Avoid Common "CG Tell" Mistakes

From Gaea's documentation:
- **Do NOT overuse Flow maps for texturing** -- makes terrain look fake and CG
- **Do NOT apply Breaker/Downcutting at high strength** -- creates obviously artificial cracks that alter perceived scale
- **Do NOT rely on single erosion pass** -- always chain multiple passes
- **LookDev nodes can create believable terrain WITHOUT erosion** -- erosion is not always mandatory as a final step

### Smooth Gradients and Anti-Aliasing

- Thermal erosion's **anisotropy** parameter smooths terrain while eroding, creating natural gradients
- Sediment deposition fills sharp valleys naturally
- The SpawningPool memory manager ensures **consistent memory locality** for data-intensive erosion, avoiding computational artifacts
- SPMD + SIMD parallelism processes billions of data points simultaneously for smooth, continuous results

---

## 4. Biome / Texturing System

### Core Philosophy

All texturing in Gaea follows one principle: **flow color gradients into black-and-white masks**.

Gradients map to terrain properties:
- Lowest gradient value = lowest terrain area
- Highest gradient value = peaks
- Mid-tones distributed by gray intensity

### The Texturing Pipeline

```
[Data Map masks] --> [Gradient/SatMap color] --> [Combine/Blend] --> [Export splatmap]
```

### Data Maps (The Foundation)

Data Maps extract physical terrain characteristics as grayscale masks:

| Data Map | What It Captures | Texturing Use |
|----------|-----------------|---------------|
| **Height/Altitude** | Elevation | Snow line, vegetation zones, rock exposure |
| **Slope** | Surface angle | Cliff face vs flat ground material selection |
| **Curvature** | Convex/concave | Ridge exposure, valley moisture |
| **Flow** | Water accumulation paths | River beds, erosion coloring (use sparingly!) |
| **Velocity** | Water speed | Exposed rock in fast-flow areas |
| **Soil** | Organic deposit analysis | Vegetation-capable areas |
| **Wear** (from Erosion) | Where material was removed | Exposed rock faces |
| **Deposits** (from Erosion) | Where sediment settled | Loose soil, sand, gravel |

**Critical insight from Gaea docs:** Data Maps "break the traditional basic data (slope, angle, etc) + chaos (Perlin noise) method." Instead of adding random noise, they derive visual randomness from "systematic analysis of the terrain and follows natural principles" -- producing **more believable** results.

### Material Mapping Strategy (What Gaea Artists Actually Do)

1. **Base layer**: CLUTer or SatMap driven by Height -- overall altitude-based coloring
2. **Cliff/rock layer**: SatMap driven by Slope mask (e.g., 64-degree slope with 13% falloff)
3. **Vegetation band**: Mapped to specific slope range where plants grow (between steep cliffs and muddy flows)
4. **Soil/dirt layer**: Driven by Soil data map with dark SatMap and jitter for gritty texture
5. **Snow/ice layer**: Height + Slope mask (accumulates on flat areas above snowline)
6. **Flow coloring**: Very subtle flow-based darkening (NOT prominent -- this is the #1 CG tell)
7. **Wind streaks**: Surfacer Wind Streaks mode, blended with Min mode for directional disturbance
8. **Wear/exposure**: Wear map from erosion drives exposed rock on ridges

### SatMaps (Satellite-Derived Gradients)

- 1400+ presets based on actual satellite photography
- Categories: mountains, deserts, forests, volcanic, arctic
- Applied via masks to specific terrain zones
- Multiple SatMaps layered creates material intermingling from erosion

### Biome Coloring

Colors terrain based on:
- Access to fresh water
- Flow areas
- Altitude zones
- Growth simulation (where vegetation can establish)

---

## 5. Export Formats and Resolution

### Supported Resolutions

| Resolution | Pixels | Use Case |
|-----------|--------|----------|
| 1024 | 1K x 1K | Preview / prototyping |
| 2048 | 2K x 2K | Small terrain tiles |
| 4096 | 4K x 4K | Standard game terrain |
| 8192 | 8K x 8K | High-detail terrain |
| 16384 | 16K x 16K | Ultra-detail / film |
| 32768 | 32K x 32K | Tiled build only |

For resolutions beyond 16K, Gaea uses **Tiled Build** to handle unlimited resolutions on modest hardware.

### File Formats

**Heightmap / Grayscale:**
| Format | Bit Depth | Best For |
|--------|-----------|----------|
| OpenEXR (.exr) | 32-bit | Maximum precision heightfields |
| TIFF (.tif) | 32-bit, 16-bit | High precision, wide compatibility |
| PNG (.png) | 32-bit, 16-bit, 8-bit | Masks, color maps, web |
| RAW (.raw) | 32-bit, 16-bit | Game engine import (stores 0-65535 for 16-bit) |
| PSD (.psd) | 32-bit | Photoshop pipeline |
| R32 (.r32) | 32-bit float | Gaea roundtrip (0.0-1.0 float range) |
| PFM (.pfm) | 32-bit float | Portable float map |

**Mesh Export:**
| Format | Use Case |
|--------|----------|
| Wavefront OBJ (.obj) | Universal mesh exchange |
| Autodesk FBX (.fbx) | Game engine / DCC import |
| Point Cloud (.xyz) | Debris, scatter data |

**Color Spaces:** RGB, sRGB, scRGB

### What Gets Exported

A typical Gaea build exports:
1. **Heightmap** (32-bit EXR or 16-bit RAW) -- the terrain elevation data
2. **Normal map** -- surface normals derived from heightfield
3. **Splatmaps** (grayscale masks) -- one per material layer (slope, altitude, flow, wear, deposits)
4. **Color/albedo map** -- pre-composed terrain color
5. **Flow map** -- water flow paths
6. **Curvature map** -- surface curvature data
7. **Wear map** -- erosion exposure data
8. **Deposit map** -- sediment location data

### Output Range Modes

| Mode | Range | Use |
|------|-------|-----|
| Raw | 0..1 natural scale | Default |
| Proportional | Matches terrain definition | Engine-specific |
| Normalized | Full 0..1 range | Maximum dynamic range |
| Custom | User-defined | Special cases |

### Unity-Specific Export

- **Resample option** for Unity terrain compatibility
- Height values normalized 0-1 (Unity Terrain expects this)
- Splatmap channels map to Unity Terrain Layers
- Gaea 3.0 will add native Unity plugin (expected mid-2026)

---

## 6. Gaea 2 / Gaea 3 and Engine Integration

### Gaea 2.x (Current)

- Erosion_2 node: GPU-accelerated hydraulic erosion with orographic rainfall
- ThermalShaper: GPU-rewritten thermal weathering
- Snow/Ice simulation nodes (Gaea 2.2)
- Selective Erosion with mask/slope/altitude precipitation control
- Deterministic mode for reproducible builds
- Build Manager with mutation system (up to 99 variations)

### Gaea 3.0 (In Development, Expected mid-2026)

- **World Space**: True infinite terrain, not single square
- **TOR Engine 3.0**: Next-gen simulation core
- **Sand/Aeolian Simulation**: Wind-driven dune formation
- **Advanced Rivers**: User-guided + natural meander
- **2.7D Displacement**: Triplanar support for overhangs
- **Native USD Support**: Roundtripping terrain data
- **Gaea SDK (C#)**: Programmatic access with optional C++ binding
- **Plugin Expansions**: Native plugins for Unity, Blender, Maya, 3ds Max
- **Renderer 3.0**: Large-scale GI for 2.5D terrains
- **EcoSystem Tools**: Layered ecosystems with dead zones
- **Vector Tools**: Precision drawing for rivers, roads, lakes

### Current Engine Integration

**Unity:**
- Export heightmap as 16-bit RAW (Unity terrain native format)
- Export splatmaps as 8/16-bit PNG (one per terrain layer)
- Use Resample option in Build Manager for Unity-compatible resolution
- No native runtime streaming yet (Gaea 3.0 will add this)

**Blender (Our Pipeline):**
- Export heightmap as 32-bit EXR for maximum precision
- Import as displacement on subdivided plane (Displacement modifier or shader)
- Export masks as 16-bit PNG for material mixing
- Export mesh as OBJ/FBX for direct geometry import

---

## 7. Parameters That Matter Most

### Erosion Parameters (Priority Order)

| Parameter | Impact | Recommended Range | Why It Matters |
|-----------|--------|-------------------|----------------|
| **Duration** | Overall erosion amount | 2-30% (multi-pass) | Too high = over-eroded mush. Too low = still procedural |
| **Feature Scale** | Valley/ridge width | Scene-dependent | THE primary artistic control for scale perception |
| **Downcutting** | Channel depth | 0-100% | Creates dramatic canyons vs gentle valleys |
| **Rock Softness** | Erosion resistance variation | 0.3-0.7 | Heterogeneous = realistic; uniform = CG |
| **Strength** | Sediment transport capacity | 0.3-0.8 | Determines deposit pattern richness |
| **Inhibition** | Deposit proximity to source | 0-50% | Low = far transport (rivers); High = local talus |
| **Base Level** | Deposition floor | 0-30% | Creates flat valley floors and basins |
| **Selective Processing mask** | Regional variation | Per-use | Without this, erosion is too uniform |
| **Seed** | Random pattern | Any integer | Use for reproducibility and variation |

### Thermal Parameters

| Parameter | Impact | Recommended Range |
|-----------|--------|-------------------|
| **Anisotropy** | Deposit shape + smoothing | 0.2-0.6 (higher = more smoothing, less preservation) |
| **Talus Angle** | Debris pile steepness | 30-45 degrees (realistic rock angle of repose) |
| **Fine Detail** | Enables rock debris | ON for close-up, OFF for distant |

### Multi-Pass Recipe (Gaea Best Practice)

```
Pass 1: Duration=30%, Selective=Altitude, Feature Scale=Large
  --> Creates macro-scale mountain drainage
Pass 2: Downcutting=100%, Base Level=moderate
  --> Carves deep channels and river beds
Pass 3: Default settings, low Duration
  --> Homogenizes and smooths while preserving structure
Pass 4 (optional): Thermal, moderate Anisotropy
  --> Adds talus deposits and smooths sharp CG edges
Pass 5 (optional): Fluvial, low Duration
  --> Adds fine carved detail on top of everything
```

---

## 8. Principles to Replicate in Our Blender Pipeline

### Must-Have Algorithms

1. **Hydraulic Erosion**: Particle-based water simulation with sediment transport, dissolve/deposit cycle
2. **Thermal Erosion**: Slope-failure with talus angle threshold, debris accumulation at base of slopes
3. **Multi-Pass Chaining**: Different erosion parameters per pass, not just running same erosion longer
4. **Selective/Masked Erosion**: Different rock hardness, precipitation, and erosion strength per region
5. **Data Map Generation**: Compute slope, curvature, flow accumulation, altitude masks from heightfield

### Must-Have Texturing

1. **Slope-based material assignment**: Steep = rock/cliff; gentle = grass/soil
2. **Altitude-based zones**: Snow line, tree line, vegetation zones
3. **Curvature-based detail**: Exposed ridges, moisture-collecting valleys
4. **Flow-based subtle coloring**: Very light darkening along water paths (NOT prominent)
5. **Wear/deposit maps from erosion**: Drive exposed rock vs loose soil materials
6. **Layered composition**: Multiple material layers blended by masks, not single texture

### Must-Avoid Pitfalls

1. **Single-pass erosion** -- always chain 2-4 passes minimum
2. **Prominent flow-map texturing** -- the #1 CG tell according to Gaea docs
3. **Uniform erosion parameters** -- real terrain has heterogeneous rock hardness
4. **Noise-based texturing without data maps** -- use slope/curvature/flow, not just Perlin noise overlay
5. **Too-high Breaker/Downcutting** -- creates obviously artificial cracks
6. **Missing thermal erosion** -- smoothing + talus is what makes ridges look natural
7. **Resolution-dependent algorithms** -- erosion must work at feature scale, not pixel scale

---

## Sources

### Primary (HIGH confidence)
- [Gaea Erosion Node Documentation](https://docs.quadspinner.com/Reference/Erosion/Erosion.html) -- full parameter reference
- [Gaea Eroding Terrains Guide](https://docs.quadspinner.com/Guide/Using-Gaea/Erosion.html) -- multi-pass techniques, best practices
- [Gaea Thermal Node Documentation](https://docs.quadspinner.com/Reference/Erosion/Thermal.html) -- thermal erosion parameters
- [Gaea Fluvial Node Documentation](https://docs.quadspinner.com/Reference/Erosion/Fluvial.html) -- fluvial erosion parameters
- [Gaea Breaker Node Documentation](https://docs.quadspinner.com/Reference/Erosion/Breaker.html) -- crack formation
- [Gaea Stratify Node Documentation](https://docs.quadspinner.com/Reference/Erosion/Stratify.html) -- geological layering
- [Gaea SlopeNoise Node Documentation](https://docs.quadspinner.com/Reference/Primitives/SlopeNoise.html) -- slope generator
- [Gaea File Formats Guide](https://docs.quadspinner.com/Guide/Using-Gaea/FileFormats.html) -- export formats and bit depths
- [Gaea Build Manager Documentation](https://docs.quadspinner.com/Guide/Build/Manager.html) -- export system
- [Gaea Color Production Guide](https://docs.quadspinner.com/Guide/Using-Gaea/Color-Production.html) -- texturing system
- [Gaea LookDev Guide](https://docs.quadspinner.com/Guide/Using-Gaea/LookDev.html) -- surface detail nodes
- [Gaea Simulations Overview](https://quadspinner.com/Gaea/Simulations) -- all simulation capabilities

### Secondary (MEDIUM confidence)
- [Gaea 3.0 Development Blog](https://blog.quadspinner.com/gaea-3-0-now-in-development/) -- upcoming features
- [Just a Terrain App: Hidden Depths Part 1](https://blog.quadspinner.com/terrain-app1/) -- engine architecture (SPMD/SIMD, SpawningPool)
- [Crafting Procedural Textures (Medium)](https://medium.com/quadspinner/crafting-procedural-textures-f95dda57120b) -- texturing workflow
- [CG Channel: Gaea 2.2 Release](https://www.cgchannel.com/2025/07/quadspinner-releases-gaea-2-2/) -- Gaea 2.2 features
- [CG Channel: Gaea 3.0 Announcement](https://www.cgchannel.com/2025/12/quadspinner-unveils-gaea-3-0/) -- Gaea 3.0 overview
- [Gaea Erosion2 (Gaea 2 Docs)](https://docs.gaea.app/node-reference/nodes/simulate/erosion2) -- Erosion2 parameters
- [80.lv: Gaea 2.2 Update](https://80.lv/articles/quadspinner-s-gaea-received-major-update) -- feature summary
