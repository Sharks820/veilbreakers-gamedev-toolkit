# Terrain Erosion & Generation: Open Source Algorithms Research

**Researched:** 2026-04-02
**Domain:** Hydraulic/thermal erosion, noise-based terrain generation, anti-jagging, neural terrain
**Confidence:** HIGH (primary sources are GitHub repos with MIT licenses + peer-reviewed papers)
**Target:** VeilBreakers Python/Blender terrain pipeline (numpy arrays, no GPU requirement)

---

## Summary

This research catalogs open source erosion algorithms, noise libraries, anti-artifact techniques, and neural terrain generation methods suitable for adaptation into VeilBreakers' existing `_terrain_erosion.py` and `_terrain_noise.py` modules. The current toolkit already has a working droplet-based hydraulic erosion (Sebastian Lague-style) and vectorized thermal erosion. The primary gaps are: (1) grid-based shallow-water hydraulic erosion (Mei et al.), (2) stream power fluvial erosion, (3) anti-jagging post-processing, (4) river network generation via watershed, and (5) domain warping for organic noise.

**Primary recommendation:** Implement grid-based (Mei et al.) hydraulic erosion as a numpy-vectorized alternative to the existing droplet method -- it parallelizes naturally across the heightmap and produces more uniform results at large scales. Add domain warping and bilateral filtering as anti-artifact passes. Defer neural/diffusion terrain to a future phase (requires GPU + training data).

---

## 1. Sebastian Lague's Hydraulic Erosion

**Source:** https://github.com/SebLague/Hydraulic-Erosion (MIT License)
**Confidence:** HIGH -- source code directly inspected

### Algorithm Summary

Particle-based (droplet) simulation. Each iteration spawns one water droplet at a random position and simulates it flowing downhill for up to `maxDropletLifetime` steps.

### Core Parameters

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| erosionRadius | 3 | 2-8 | Precomputed brush kernel radius |
| inertia | 0.05 | 0-1 | Direction smoothing (0=follow gradient, 1=keep direction) |
| sedimentCapacityFactor | 4.0 | 1-10 | Multiplier for carrying capacity |
| minSedimentCapacity | 0.01 | - | Floor to prevent zero capacity on flat terrain |
| erodeSpeed | 0.3 | 0-1 | Fraction of capacity deficit eroded per step |
| depositSpeed | 0.3 | 0-1 | Fraction of excess sediment deposited per step |
| evaporateSpeed | 0.01 | 0-1 | Water loss per step |
| gravity | 4.0 | - | Acceleration constant for speed updates |
| maxDropletLifetime | 30 | - | Max simulation steps per droplet |

### Key Formulas

```
// Gradient via bilinear interpolation of 4 surrounding heights
grad_x = (h10 - h00) * (1 - fy) + (h11 - h01) * fy
grad_y = (h01 - h00) * (1 - fx) + (h11 - h10) * fx

// Direction update with inertia
dir_x = dir_x * inertia - grad_x * (1 - inertia)
dir_y = dir_y * inertia - grad_y * (1 - inertia)
// then normalize

// Sediment capacity
capacity = max(-deltaHeight * speed * water * sedimentCapacityFactor, minSedimentCapacity)

// Deposition: when sediment > capacity OR moving uphill
deposit = (sediment - capacity) * depositSpeed  // or min(sediment, deltaHeight) if uphill

// Erosion: when sediment < capacity AND moving downhill
erode = min((capacity - sediment) * erodeSpeed, -deltaHeight)

// Speed update
speed = sqrt(speed^2 + deltaHeight * gravity)

// Water evaporation
water *= (1 - evaporateSpeed)
```

### Erosion Brush System

Precomputed per-radius. For each cell within radius, weight = `1 - sqrt(dx^2 + dy^2) / radius`. All weights normalized to sum to 1. This distributes erosion smoothly across neighbors rather than punching single-pixel holes.

### VeilBreakers Current Status

**Already implemented** in `_terrain_erosion.py::apply_hydraulic_erosion()`. The implementation is faithful to Lague's algorithm. However, it uses Python `for` loops per droplet step -- NOT vectorizable because each droplet is sequential. For 10,000+ iterations on 512x512, this is slow (~5-10 seconds).

### Optimization Opportunities

1. **Numba JIT**: Wrap the inner droplet loop with `@numba.jit(nopython=True)` for 50-100x speedup
2. **Batch droplets**: Process N droplets in parallel using numpy arrays (positions, velocities as Nx2 arrays). Requires handling collisions but gives massive speedup
3. **C extension**: Port inner loop to C via cffi/ctypes for maximum throughput

---

## 2. Grid-Based Hydraulic Erosion (Mei et al. / Shallow Water)

**Paper:** "Fast Hydraulic Erosion Simulation and Visualization on GPU" -- Xing Mei, Philippe Decaudin, Bao-Gang Hu (Pacific Graphics 2007)
**PDF:** https://inria.hal.science/inria-00402079/document
**Python impl:** https://github.com/keepitwiel/hydraulic-erosion-simulator
**Confidence:** HIGH -- peer-reviewed paper + multiple implementations

### Algorithm Overview

Unlike droplet-based, this simulates water as a continuous field over the entire grid. Each cell stores: terrain height (b), water height (d), sediment concentration (s), and outflow flux to 4 neighbors (fL, fR, fT, fB).

### Simulation Steps Per Iteration

1. **Water increment:** Add rain/water to each cell: `d += dt * rain_rate`
2. **Flow simulation (pipe model):**
   ```
   // For each direction (L, R, T, B):
   f_new = max(0, f_old + dt * g * A * delta_h / l)
   // where delta_h = (b1 + d1) - (b2 + d2), A = pipe cross-section, l = pipe length
   
   // Scale flows to prevent negative water:
   K = min(1, d * lx * ly / (sum_of_all_outflows * dt))
   f_new *= K
   ```
3. **Water surface update:** `d += dt * (sum_inflows - sum_outflows) / (lx * ly)`
4. **Velocity field:** Compute (u, v) from flow differences: `u = (fL_left - fL_right + fR_left - fR_right) / 2`
5. **Erosion/deposition:**
   ```
   capacity = Kc * ||velocity|| * sin(slope) * water_depth
   if sediment > capacity: deposit (sediment - capacity) * Kd
   if sediment < capacity: erode (capacity - sediment) * Ks
   ```
6. **Sediment transport:** Advect sediment field using velocity: `s_new[x,y] = s[x - u*dt, y - v*dt]` (bilinear interpolation)
7. **Evaporation:** `d *= (1 - Ke * dt)`

### Why This Matters for VeilBreakers

**Fully vectorizable with numpy.** Every step operates on the entire grid simultaneously -- no per-particle loops. Steps 1-7 are all array operations: `np.roll`, `np.maximum`, element-wise multiply, `scipy.ndimage.map_coordinates` for advection.

### Key Parameters

| Parameter | Symbol | Typical Value | Purpose |
|-----------|--------|---------------|---------|
| Pipe cross-section area | A | 1.0 | Flow rate scaling |
| Gravity | g | 9.81 | Hydrostatic pressure |
| Sediment capacity | Kc | 0.01-0.1 | How much sediment water can carry |
| Suspension rate | Ks | 0.01-0.05 | How fast sediment enters water |
| Deposition rate | Kd | 0.01-0.05 | How fast sediment leaves water |
| Evaporation rate | Ke | 0.01 | Water loss per step |
| Time step | dt | 0.01-0.05 | Stability depends on CFL condition |
| Rain rate | Kr | 0.01 | Water added per step per cell |

### Implementation Skeleton (numpy)

```python
def grid_hydraulic_erosion(heightmap, iterations=200, dt=0.02, Kc=0.05, Ks=0.02, Kd=0.02, Ke=0.01, rain=0.01):
    h, w = heightmap.shape
    b = heightmap.astype(np.float64).copy()  # terrain height
    d = np.zeros_like(b)                      # water depth
    s = np.zeros_like(b)                      # sediment
    fL = np.zeros_like(b)                     # flux left
    fR = np.zeros_like(b)                     # flux right
    fT = np.zeros_like(b)                     # flux top
    fB = np.zeros_like(b)                     # flux bottom
    
    g = 9.81
    for _ in range(iterations):
        # 1. Rain
        d += dt * rain
        
        # 2. Outflow flux (pipe model)
        surface = b + d
        delta_L = surface - np.roll(surface, 1, axis=1)
        delta_R = surface - np.roll(surface, -1, axis=1)
        delta_T = surface - np.roll(surface, 1, axis=0)
        delta_B = surface - np.roll(surface, -1, axis=0)
        
        fL = np.maximum(0, fL + dt * g * delta_L)
        fR = np.maximum(0, fR + dt * g * delta_R)
        fT = np.maximum(0, fT + dt * g * delta_T)
        fB = np.maximum(0, fB + dt * g * delta_B)
        
        # Scale to prevent negative water
        total_out = fL + fR + fT + fB
        K = np.minimum(1.0, d / (total_out * dt + 1e-10))
        fL *= K; fR *= K; fT *= K; fB *= K
        
        # 3. Update water depth
        inflow = (np.roll(fR, 1, axis=1) + np.roll(fL, -1, axis=1) +
                  np.roll(fB, 1, axis=0) + np.roll(fT, -1, axis=0))
        d += dt * (inflow - (fL + fR + fT + fB))
        d = np.maximum(d, 0)
        
        # 4. Velocity field
        u = (np.roll(fR, 1, axis=1) - fL + fR - np.roll(fL, -1, axis=1)) * 0.5
        v = (np.roll(fB, 1, axis=0) - fT + fB - np.roll(fT, -1, axis=0)) * 0.5
        vel_mag = np.sqrt(u**2 + v**2)
        
        # 5. Erosion/deposition
        slope = compute_slope(b)  # gradient magnitude
        capacity = Kc * vel_mag * np.sin(np.radians(slope)) * d
        
        deposit_mask = s > capacity
        erode_mask = ~deposit_mask
        
        b[deposit_mask] += (s[deposit_mask] - capacity[deposit_mask]) * Kd
        s[deposit_mask] -= (s[deposit_mask] - capacity[deposit_mask]) * Kd
        
        b[erode_mask] -= (capacity[erode_mask] - s[erode_mask]) * Ks
        s[erode_mask] += (capacity[erode_mask] - s[erode_mask]) * Ks
        
        # 6. Sediment transport (advection via scipy)
        # s_new[x,y] = s[x - u*dt, y - v*dt]  -- bilinear interpolation
        
        # 7. Evaporation
        d *= (1 - Ke * dt)
    
    return np.clip(b, 0, 1)
```

### Performance Estimate

On 512x512 with 200 iterations: ~2-5 seconds with pure numpy. With numba: ~0.2-0.5 seconds.

---

## 3. GPU-Accelerated Erosion Repositories

### Key Repos

| Repository | Language | Erosion Types | License | Stars | Relevance |
|------------|----------|---------------|---------|-------|-----------|
| [bshishov/UnityTerrainErosionGPU](https://github.com/bshishov/UnityTerrainErosionGPU) | C#/HLSL | Hydraulic (shallow water) + Thermal | MIT | ~700 | Algorithm reference for compute shader approach |
| [GPU-Gang/WebGPU-Erosion-Simulation](https://github.com/GPU-Gang/WebGPU-Erosion-Simulation) | TS/WebGPU | Stream power (Cordonnier) | MIT | ~100 | Parallel drainage area approximation |
| [simonmeister/hydraulic-terrain-modeler](https://github.com/simonmeister/hydraulic-terrain-modeler) | C++/CUDA | Hydraulic with water sim | MIT | ~150 | CUDA reference for future GPU port |
| [Huw-man/Interactive-Erosion-Simulator-on-GPU](https://huw-man.github.io/Interactive-Erosion-Simulator-on-GPU/) | C++/OpenGL | Shallow water hydraulic | - | - | Interactive demo + compute shader patterns |
| [dandrino/terrain-erosion-3-ways](https://github.com/dandrino/terrain-erosion-3-ways) | Python | Simulation + GAN + River networks | MIT | ~1500 | **Directly portable to VeilBreakers** |

### Axel Paris GPU Erosion Analysis

Blog: https://aparis69.github.io/public_html/posts/terrain_erosion.html

Key insight on GPU race conditions: **Ignoring race conditions in a single float buffer** still produces visually correct erosion after a few extra iterations. The non-determinism is acceptable for terrain generation. Three GPU approaches tested:

1. **Single Integer Buffer** -- Fast but precision-limited, good for large-scale only
2. **Double Buffer** -- Floating-point via atomic bitwise conversion, deterministic
3. **Single Float Buffer** -- Simplest, tolerates race conditions, fastest overall

**Recommendation for VeilBreakers:** We run on CPU (numpy), so race conditions are not an issue. But the "tolerate imprecision" philosophy applies to our vectorized grid erosion -- small numerical errors from parallel np.roll operations are acceptable.

---

## 4. Academic Papers on Terrain Erosion

### Paper 1: Mei et al. 2007 -- "Fast Hydraulic Erosion Simulation and Visualization on GPU"

**Citation:** Xing Mei, Philippe Decaudin, Bao-Gang Hu. Pacific Graphics 2007.
**PDF:** https://inria.hal.science/inria-00402079/document
**Confidence:** HIGH

- Introduced the pipe model for GPU-parallel shallow water erosion
- 5 simulation layers: water, flux (4 directions), velocity, sediment, terrain
- CFL stability condition: `dt < min(lx, ly) / (g * max_water_depth)`
- Foundation for nearly all grid-based erosion implementations since

### Paper 2: Schott et al. 2023 -- "Large-scale Terrain Authoring through Interactive Erosion Simulation"

**Citation:** ACM Transactions on Graphics 42, 2023.
**PDF:** https://hal.science/hal-04049125/document
**Confidence:** HIGH

- Works in **uplift domain** rather than elevation domain
- Stream power erosion: `dh/dt = U - K * A^m * S^n` where A=drainage area, S=slope, U=uplift
- Key innovation: **parallel approximation of drainage area** -- converges in O(log n) iterations
- Provides copy-paste, warping, and curve constraint tools for artists
- Directly inspires the WebGPU-Erosion-Simulation repo

### Paper 3: Tzathas et al. 2024 -- "Physically-based Analytical Erosion for Fast Terrain Generation"

**Citation:** Computer Graphics Forum (Eurographics 2024), DOI: 10.1111/cgf.15033
**PDF:** http://www-sop.inria.fr/reves/Basilic/2024/TGSC24/Analytical_Terrains_EG.pdf
**Confidence:** HIGH

- Derives **analytical (closed-form) solutions** to the stream power law
- Time becomes a parameter of a function, not a stopping criterion of iteration
- Slider-based control: from subtle erosion to fully formed mountain ranges
- Multigrid acceleration for the iterative solver
- Incorporates landslides and hillslope processes alongside fluvial erosion
- **Most relevant recent paper** -- could enable "erosion age" parameter in VeilBreakers

### Paper 4: Jain et al. 2024 -- "FastFlow: GPU Acceleration of Flow and Depression Routing"

**Citation:** Computer Graphics Forum, October 2024, DOI: 10.1111/cgf.15243
**Confidence:** HIGH

- GPU flow routing in O(log n) iterations for n vertices
- Depression routing converges in O(log^2 n) iterations
- Enables real-time large-scale landscape simulation
- Depression filling is critical for avoiding "lakes" that trap erosion

### Musgrave's Terrain Generation Methods

**Source:** "Texturing & Modeling: A Procedural Approach" (Ebert, Musgrave, et al.)
**Reference implementation:** https://engineering.purdue.edu/~ebertd/texture/1stEdition/musgrave/musgrave.c
**Confidence:** HIGH -- canonical reference, already partially in VeilBreakers

Four noise types for terrain:

1. **fBm** -- Standard fractional Brownian motion. Smooth, round hills.
2. **Ridged Multifractal** -- `signal = offset - abs(noise(p)); signal *= signal` -- creates sharp ridges from zero-crossings. **Already documented in TERRAIN_SCULPTING_AAA_TECHNIQUES.md.**
3. **Hybrid Multifractal** -- Combines additive and multiplicative cascades. Smooth valleys + rough peaks. Best for natural-looking landscapes.
4. **Heterogeneous Terrain** -- Produces river-channel-like features. Varies smoothness based on altitude.

**VeilBreakers status:** `_terrain_noise.py` uses basic fBm. Ridged and hybrid multifractal are documented in AAA research but NOT yet implemented in code.

---

## 5. Key Open Source Repositories

### Directly Portable to Python/NumPy

| Repository | What It Does | Key Files | Port Difficulty |
|------------|-------------|-----------|-----------------|
| [dandrino/terrain-erosion-3-ways](https://github.com/dandrino/terrain-erosion-3-ways) | 3 erosion methods: simulation, GAN, river networks | Python + numpy already | **TRIVIAL** -- already Python |
| [keepitwiel/hydraulic-erosion-simulator](https://github.com/keepitwiel/hydraulic-erosion-simulator) | Mei et al. pipe model in pure Python | `src/algorithm.py` | **TRIVIAL** -- already Python |
| [SebLague/Hydraulic-Erosion](https://github.com/SebLague/Hydraulic-Erosion) | Droplet-based (C#/Unity) | `Assets/Scripts/Erosion.cs` | **Already ported** in `_terrain_erosion.py` |
| [christopher-beckham/gan-heightmaps](https://github.com/christopher-beckham/gan-heightmaps) | GAN terrain from NASA data | TensorFlow | MEDIUM -- needs training |
| [liquidnode/neural_terrain_2](https://github.com/liquidnode/neural_terrain_2) | Two-stage GAN heightmaps | Python + TF | MEDIUM -- needs training |

### Noise Libraries

| Library | Python Package | Version | Features | Speed |
|---------|---------------|---------|----------|-------|
| **OpenSimplex** | `opensimplex` | 0.4.5.1 | 2D/3D/4D simplex, numpy vectorized | Fast, **already installed** |
| **PyFastNoiseLite** | `pyfastnoiselite` | 0.0.7 | OpenSimplex2, cellular, Perlin, value, domain warp | Fastest (C backend) |
| **noise** (Perlin) | `noise` | 1.2.2 | Perlin 2D/3D, simplex | Moderate |
| **heman** | `heman` | - | Island generation, lighting, distance fields | C backend, niche |

**Recommendation:** Continue using `opensimplex` (already a dependency). Add `pyfastnoiselite` only if domain warp or cellular noise is needed -- it wraps C code and is significantly faster for batch evaluation.

### Watershed / River Network Libraries

| Library | Package | Purpose |
|---------|---------|---------|
| **pysheds** | `pysheds` | Watershed delineation, stream network extraction from DEM |
| **scipy.ndimage** | `scipy` | `watershed_ift` for basin segmentation |
| **scikit-image** | `scikit-image` | `watershed` with distance transforms |

**Recommendation:** Use `scipy.ndimage.watershed_ift` for basic basin detection (no extra dependency). Use `pysheds` only if real hydrological accuracy is needed.

---

## 6. NumPy/SciPy Terrain Algorithm Patterns

### Fast Heightmap Erosion with NumPy

```python
# Grid-based thermal erosion -- fully vectorized, no loops
def thermal_erosion_vectorized(hmap, iterations=10, talus=0.04):
    """Vectorized thermal erosion using np.roll for neighbor access."""
    h = hmap.copy()
    offsets = [(0,1), (0,-1), (1,0), (-1,0), (1,1), (1,-1), (-1,1), (-1,-1)]
    dists = [1.0, 1.0, 1.0, 1.0, 1.414, 1.414, 1.414, 1.414]
    
    for _ in range(iterations):
        max_diff = np.zeros_like(h)
        total_diff = np.zeros_like(h)
        
        for (dy, dx), dist in zip(offsets, dists):
            neighbor = np.roll(np.roll(h, -dy, axis=0), -dx, axis=1)
            slope = (h - neighbor) / dist
            excess = np.maximum(slope - talus, 0)
            total_diff += excess
            max_diff = np.maximum(max_diff, excess)
        
        transfer = max_diff * 0.5
        has_transfer = total_diff > 0
        
        for (dy, dx), dist in zip(offsets, dists):
            neighbor = np.roll(np.roll(h, -dy, axis=0), -dx, axis=1)
            slope = (h - neighbor) / dist
            excess = np.maximum(slope - talus, 0)
            frac = np.where(has_transfer, excess / (total_diff + 1e-10), 0)
            amount = transfer * frac
            h -= amount
            h += np.roll(np.roll(amount, dy, axis=0), dx, axis=1)
    
    return np.clip(h, 0, 1)
```

### Gaussian Filtering for Smooth Terrain

```python
from scipy.ndimage import gaussian_filter

# Smooth terrain with controllable radius
smoothed = gaussian_filter(heightmap, sigma=2.0)

# Altitude-dependent smoothing (smooth valleys more than peaks)
altitude_mask = np.clip(heightmap, 0.3, 0.7)
altitude_mask = (altitude_mask - 0.3) / 0.4  # 0 at valley, 1 at peak
mixed = smoothed * (1 - altitude_mask) + heightmap * altitude_mask
```

### Gradient / Slope Map Calculation

```python
# Compute slope in degrees using numpy gradient
def compute_slope_degrees(heightmap, cell_size=1.0):
    gy, gx = np.gradient(heightmap, cell_size)
    slope_radians = np.arctan(np.sqrt(gx**2 + gy**2))
    return np.degrees(slope_radians)

# Aspect map (direction of steepest descent)
def compute_aspect(heightmap, cell_size=1.0):
    gy, gx = np.gradient(heightmap, cell_size)
    return np.degrees(np.arctan2(-gy, -gx)) % 360
```

### Watershed for River Networks

```python
from scipy.ndimage import label, watershed_ift
import numpy as np

def extract_river_network(heightmap, threshold=0.3):
    """Extract drainage basins and approximate river paths."""
    # Invert heightmap (watershed fills from minima)
    inverted = (1.0 - heightmap * 65535).astype(np.int32)
    
    # Create markers at local minima
    from scipy.ndimage import minimum_filter
    local_min = minimum_filter(heightmap, size=5) == heightmap
    markers, num_basins = label(local_min)
    
    # Run watershed
    basins = watershed_ift(inverted, markers)
    
    # River paths are at basin boundaries where flow accumulates
    # Use gradient to trace flow direction
    gy, gx = np.gradient(heightmap)
    flow_magnitude = np.sqrt(gx**2 + gy**2)
    
    return basins, flow_magnitude
```

### Flow Accumulation (for stream power erosion)

```python
def compute_flow_accumulation(heightmap):
    """Simple D8 flow accumulation using steepest descent."""
    rows, cols = heightmap.shape
    flow = np.ones_like(heightmap)  # each cell contributes 1 unit
    
    # Sort cells by height (highest first)
    flat_indices = np.argsort(-heightmap.ravel())
    
    offsets = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]
    dists = [1.414, 1.0, 1.414, 1.0, 1.0, 1.414, 1.0, 1.414]
    
    for idx in flat_indices:
        r, c = divmod(idx, cols)
        max_slope = 0
        target = -1
        for (dr, dc), dist in zip(offsets, dists):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                slope = (heightmap[r, c] - heightmap[nr, nc]) / dist
                if slope > max_slope:
                    max_slope = slope
                    target = nr * cols + nc
        if target >= 0:
            tr, tc = divmod(target, cols)
            flow[tr, tc] += flow[r, c]
    
    return flow
```

**Note:** The above D8 flow accumulation has O(n) Python loops over sorted cells. For large grids, use numba or implement the parallel O(log n) approach from FastFlow (Jain et al. 2024).

---

## 7. Anti-Jagging Techniques

### Problem

Grid-aligned noise produces visible horizontal/vertical artifacts (the "Minecraft effect"). Erosion along grid axes creates unnatural straight channels. Both degrade realism.

### Technique 1: Domain Warping

**What:** Offset noise sampling coordinates with another noise function before evaluation. Breaks grid alignment at the noise level.

```python
def domain_warp_heightmap(shape, scale=100, warp_strength=30, seed=0):
    """Generate heightmap with domain warping to break grid artifacts."""
    rows, cols = shape
    y, x = np.mgrid[0:rows, 0:cols].astype(np.float64)
    
    # Warp coordinates using separate noise
    from opensimplex import OpenSimplex
    warp_gen = OpenSimplex(seed=seed + 1000)
    
    # Vectorized warp (if opensimplex supports it)
    warp_x = np.zeros(shape)
    warp_y = np.zeros(shape)
    for r in range(rows):
        for c in range(cols):
            warp_x[r, c] = warp_gen.noise2(c / 80.0, r / 80.0) * warp_strength
            warp_y[r, c] = warp_gen.noise2(c / 80.0 + 5.2, r / 80.0 + 1.3) * warp_strength
    
    warped_x = x + warp_x
    warped_y = y + warp_y
    
    # Now sample primary noise at warped coordinates
    gen = OpenSimplex(seed=seed)
    heightmap = np.zeros(shape)
    for r in range(rows):
        for c in range(cols):
            heightmap[r, c] = gen.noise2(warped_x[r, c] / scale, warped_y[r, c] / scale)
    
    return (heightmap + 1) * 0.5  # normalize to [0, 1]
```

**Performance note:** The above uses Python loops. For production, either vectorize with opensimplex's array API or use pyfastnoiselite which has built-in domain warp support.

### Technique 2: Rotated Octaves

Rotate sampling coordinates by a non-axis-aligned angle between noise octaves:

```python
def rotated_fbm(x, y, octaves=6, seed=0, rotation_deg=37.0):
    """fBm with rotated octaves to eliminate axis-aligned artifacts."""
    cos_r = np.cos(np.radians(rotation_deg))
    sin_r = np.sin(np.radians(rotation_deg))
    
    value = 0.0
    amplitude = 1.0
    frequency = 1.0
    cx, cy = x, y
    
    for i in range(octaves):
        value += noise2(cx * frequency, cy * frequency, seed + i) * amplitude
        amplitude *= 0.5
        frequency *= 2.0
        # Rotate coordinates for next octave
        new_cx = cx * cos_r - cy * sin_r
        new_cy = cx * sin_r + cy * cos_r
        cx, cy = new_cx, new_cy
    
    return value
```

### Technique 3: Bilateral Filtering (Post-Process)

Smooths terrain while preserving sharp edges (cliff faces, ridgelines):

```python
def bilateral_filter_heightmap(heightmap, spatial_sigma=2.0, range_sigma=0.1):
    """Bilateral filter: smooth terrain while preserving edges."""
    from scipy.ndimage import uniform_filter
    
    rows, cols = heightmap.shape
    result = np.zeros_like(heightmap)
    
    # Approximation using guided filter approach (faster than true bilateral)
    radius = int(3 * spatial_sigma)
    
    # For production, use OpenCV's bilateralFilter or implement separable approximation
    # This is a simplified version:
    smooth = gaussian_filter(heightmap, sigma=spatial_sigma)
    diff = np.abs(heightmap - smooth)
    edge_weight = np.exp(-(diff ** 2) / (2 * range_sigma ** 2))
    result = heightmap * edge_weight + smooth * (1 - edge_weight)
    
    return result
```

**Better option:** If OpenCV is available, use `cv2.bilateralFilter(heightmap.astype(np.float32), d=5, sigmaColor=0.1, sigmaSpace=2.0)`.

### Technique 4: Multi-Resolution Blending

Generate terrain at multiple scales and blend them with smooth transitions:

```python
def multi_resolution_terrain(shape, scales=[400, 100, 25, 6], weights=[0.4, 0.3, 0.2, 0.1], seed=0):
    """Generate terrain by blending multiple noise scales."""
    result = np.zeros(shape, dtype=np.float64)
    
    for scale, weight in zip(scales, weights):
        layer = generate_noise_layer(shape, scale=scale, seed=seed)
        # Apply gaussian blur at appropriate radius for this scale
        blur_radius = max(1, scale / 50)
        layer = gaussian_filter(layer, sigma=blur_radius)
        result += layer * weight
        seed += 1
    
    # Normalize
    result = (result - result.min()) / (result.max() - result.min() + 1e-10)
    return result
```

### Technique 5: Simplex Over Perlin

Use OpenSimplex or Simplex noise instead of Perlin. Simplex has no axis-aligned gradient artifacts by construction. **VeilBreakers already uses OpenSimplex -- this is correct.**

### Technique 6: Jittered Sampling

Add small random offsets to grid sampling points:

```python
def jittered_noise(shape, scale=100, jitter=0.4, seed=0):
    """Sample noise with jittered grid positions."""
    rows, cols = shape
    rng = np.random.RandomState(seed)
    
    y, x = np.mgrid[0:rows, 0:cols].astype(np.float64)
    x += rng.uniform(-jitter, jitter, shape)
    y += rng.uniform(-jitter, jitter, shape)
    
    # Sample noise at jittered positions
    return sample_noise_2d(x / scale, y / scale, seed)
```

---

## 8. Neural / ML Terrain Generation

### Current State of the Art (2024-2025)

| Method | Paper/Repo | Year | Type | Training Data | Quality |
|--------|-----------|------|------|---------------|---------|
| **TerraFusion** | arxiv 2505.04050 | 2025 | Latent Diffusion | Real-world terrain | Joint heightmap + texture |
| **MESA** | CVPR 2025 Workshop | 2025 | Latent Diffusion | Copernicus satellite DEM | Text-to-terrain |
| **Terrain Diffusion** | arxiv 2512.08309 | 2025 | Latent Diffusion | Real elevation data | Infinite real-time |
| **Lochner 2023** | CGF/EG 2023 | 2023 | Diffusion | - | Interactive authoring |
| **GAN Heightmaps** | github.com/christopher-beckham | 2017+ | DCGAN | NASA SRTM | 512x512 heightmaps |
| **Neural Terrain 2** | github.com/liquidnode | 2020 | Two-stage GAN | - | Low-res then upsample |
| **ProGAN Terrain** | dandrino/terrain-erosion-3-ways | 2019 | Progressive GAN | USGS NED | 512x512, very realistic |

### Diffusion Models (2024-2025 Frontier)

The field has moved from GANs to **latent diffusion models**:

- **TerraFusion (2025):** Uses a VAE dedicated to heightmaps + joint denoising of height and texture. Operates in low-dimensional latent space.
- **MESA (2025):** Text-conditioned terrain generation ("Generate a mountain range with river valleys"). Uses modified U-Net with Copernicus global DEM data.
- **Terrain Diffusion (2025):** Generates 46km tiles; consistency decoder expands latents to high-fidelity elevation maps. Claims to be a "successor to Perlin noise."

### Practical Assessment for VeilBreakers

| Approach | Feasible Now? | GPU Required? | Training Required? | Recommendation |
|----------|--------------|---------------|-------------------|----------------|
| Pretrained GAN (512x512) | Yes | Yes (inference) | No (use pretrained) | MEDIUM priority -- could generate base heightmaps |
| Train custom GAN | Possible | Yes (days) | Yes (need DEM data) | LOW priority -- significant effort |
| Diffusion model | Not yet | Yes (significant) | Yes | DEFER -- wait for open weights |
| Style transfer | Yes | Yes (inference) | No | MEDIUM -- apply real terrain style to noise |

**Recommendation:** Defer neural terrain to a future phase. The procedural + erosion pipeline is more controllable and deterministic (seeded). If neural terrain is desired later, start with a pretrained GAN from `christopher-beckham/gan-heightmaps` and use its outputs as base heightmaps that get refined by erosion.

---

## 9. Stream Power Erosion (Fluvial)

This is the most physically accurate erosion model for large-scale terrain (mountain ranges, river valleys).

### The Stream Power Equation

```
dh/dt = U - K * A^m * S^n
```

Where:
- `h` = terrain height
- `U` = tectonic uplift rate (how fast the ground rises)
- `K` = erosion coefficient (rock hardness)
- `A` = upstream drainage area at each point
- `S` = local slope
- `m, n` = empirical exponents (typically m=0.5, n=1.0)

### Implementation Challenge

Computing drainage area `A` requires tracing all water flow paths from every cell to the ocean. This is inherently sequential in naive implementations (topological sort). The Cordonnier/Schott parallel approximation computes it iteratively:

```python
def parallel_drainage_area(heightmap, iterations=20):
    """Approximate drainage area using iterative parallel diffusion."""
    area = np.ones_like(heightmap)  # each cell starts with area=1
    
    for _ in range(iterations):
        # For each cell, find steepest downhill neighbor
        # Add this cell's area to that neighbor
        new_area = np.ones_like(heightmap)
        
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            neighbor = np.roll(np.roll(heightmap, -dy, axis=0), -dx, axis=1)
            # Where this cell is lower than the shifted neighbor,
            # the neighbor drains to us
            receives = heightmap < neighbor
            contrib = np.roll(np.roll(area * receives, dy, axis=0), dx, axis=1)
            new_area += contrib
        
        area = new_area
    
    return area
```

**Note:** This is a simplified version. The actual Cordonnier approach uses steepest descent routing with convergence checking. See the WebGPU-Erosion-Simulation repo for the full parallel algorithm.

---

## 10. Recommended Implementation Priority

### Phase 1: Immediate Improvements (Low Effort, High Impact)

1. **Domain warping** in `_terrain_noise.py` -- break grid artifacts in noise generation
2. **Bilateral filter post-pass** in `_terrain_erosion.py` -- smooth erosion artifacts while preserving features
3. **Ridged multifractal** noise type -- already researched in AAA techniques doc, just needs code

### Phase 2: New Erosion Methods (Medium Effort, High Impact)

4. **Grid-based hydraulic erosion (Mei et al.)** -- fully vectorized numpy, complements droplet method
5. **Numba JIT on existing droplet erosion** -- 50-100x speedup for free
6. **Flow accumulation** -- D8 algorithm for drainage area, enables stream power

### Phase 3: Advanced Features (Higher Effort)

7. **Stream power erosion** -- most realistic large-scale terrain shaping
8. **River network extraction** via watershed -- connect to existing `carve_river_path`
9. **Analytical erosion (Tzathas 2024)** -- "erosion age" slider parameter

### Phase 4: Future / Experimental

10. **Neural terrain generation** -- pretrained GAN for base heightmaps (needs GPU)
11. **Diffusion-based terrain** -- wait for open weights/models

---

## Common Pitfalls

### Pitfall 1: CFL Violation in Grid-Based Erosion
**What goes wrong:** Simulation explodes (NaN/inf values) after a few iterations
**Why:** Time step `dt` too large relative to grid spacing and water depth
**Prevention:** `dt < min(cell_size_x, cell_size_y) / sqrt(g * max_water_depth)`
**Warning signs:** Values > 1.0 or < 0.0 appearing in heightmap

### Pitfall 2: Erosion Holes in Droplet Method
**What goes wrong:** Deep pits form where many droplets converge
**Why:** Not capping erosion to height difference; erosion brush too small
**Prevention:** `erode_amount = min((capacity - sediment) * erosion_rate, -h_diff)` -- already in VeilBreakers code

### Pitfall 3: Grid Artifacts from np.roll Boundary
**What goes wrong:** Wrap-around artifacts at grid edges from numpy roll
**Why:** `np.roll` wraps values from one edge to the other
**Prevention:** Pad heightmap edges before rolling, or mask edge cells. Use `np.pad(h, 1, mode='edge')` then slice.

### Pitfall 4: Slow Droplet Erosion at Large Scale
**What goes wrong:** 50,000 iterations on 1024x1024 takes minutes
**Why:** Python loop per droplet step, per droplet
**Prevention:** Numba JIT, or switch to grid-based method for large maps. Do NOT try to vectorize droplet paths -- they're inherently sequential per droplet.

### Pitfall 5: Flat Areas Trap Water
**What goes wrong:** Depressions in terrain accumulate water that never drains, creating unrealistic lakes
**Why:** No depression filling algorithm
**Prevention:** Apply depression filling before erosion (fill all local minima to their spill point). The Priority-Flood algorithm does this in O(n log n).

### Pitfall 6: Over-Smoothing Destroys Features
**What goes wrong:** Gaussian blur post-pass erases cliff faces and sharp ridges
**Why:** Isotropic smoothing doesn't respect edges
**Prevention:** Use bilateral filter or guided filter instead of gaussian. These preserve high-contrast edges.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| numpy | All algorithms | Yes | 2.4.3 | None (required) |
| scipy | Grid erosion, watershed, gaussian filter | No (not installed) | - | Implement gaussian manually or `pip install scipy` |
| opensimplex | Noise generation | Yes | 0.4.5.1 | Built-in permutation table fallback (already exists) |
| pyfastnoiselite | Domain warp, cellular noise | No | - | Manual domain warp with opensimplex |
| numba | JIT acceleration | No | - | Skip JIT, use pure numpy (slower) |
| opencv-python | Bilateral filter | No | - | Simplified bilateral with scipy/numpy |
| pysheds | Watershed/river extraction | No | - | scipy.ndimage.watershed_ift |

**Missing dependencies with no fallback:**
- scipy: Strongly recommended. Many algorithms use `gaussian_filter`, `map_coordinates`, `watershed_ift`. Should be added as dependency.

**Missing dependencies with fallback:**
- numba: Performance optimization only. Pure numpy works, just slower.
- pyfastnoiselite: Domain warp can be done manually with opensimplex.
- opencv-python: Bilateral filter can be approximated with numpy.
- pysheds: scipy.ndimage covers basic watershed needs.

---

## Sources

### Primary (HIGH confidence)
- [SebLague/Hydraulic-Erosion](https://github.com/SebLague/Hydraulic-Erosion) -- MIT license, C# droplet erosion
- [dandrino/terrain-erosion-3-ways](https://github.com/dandrino/terrain-erosion-3-ways) -- MIT license, Python/numpy, 3 methods
- [keepitwiel/hydraulic-erosion-simulator](https://github.com/keepitwiel/hydraulic-erosion-simulator) -- Mei et al. Python implementation
- [bshishov/UnityTerrainErosionGPU](https://github.com/bshishov/UnityTerrainErosionGPU) -- Compute shader erosion reference
- [GPU-Gang/WebGPU-Erosion-Simulation](https://github.com/GPU-Gang/WebGPU-Erosion-Simulation) -- Parallel stream power erosion
- Mei et al. 2007 (IEEE/INRIA): https://inria.hal.science/inria-00402079/document
- Schott et al. 2023 (ACM TOG): https://dl.acm.org/doi/10.1145/3592787
- Tzathas et al. 2024 (EG/CGF): https://onlinelibrary.wiley.com/doi/10.1111/cgf.15033
- Jain et al. 2024 (CGF): https://onlinelibrary.wiley.com/doi/10.1111/cgf.15243
- Musgrave reference implementation: https://engineering.purdue.edu/~ebertd/texture/1stEdition/musgrave/musgrave.c
- Axel Paris GPU erosion blog: https://aparis69.github.io/public_html/posts/terrain_erosion.html

### Secondary (MEDIUM confidence)
- OpenSimplex PyPI: https://pypi.org/project/opensimplex/
- PyFastNoiseLite GitHub: https://github.com/tizilogic/pyfastnoiselite
- pysheds GitHub: https://github.com/mdbartos/pysheds
- Red Blob Games noise tutorial: https://www.redblobgames.com/maps/terrain-from-noise/
- TerrainPrettifier (Unity): https://github.com/Fewes/TerrainPrettifier

### Tertiary (LOW confidence -- needs validation)
- TerraFusion (2025): https://arxiv.org/abs/2505.04050 -- preprint, not yet peer-reviewed
- MESA (2025): CVPR Workshop paper, text-to-terrain
- Terrain Diffusion (2025): https://arxiv.org/html/2512.08309 -- preprint
- GAN heightmaps: https://github.com/christopher-beckham/gan-heightmaps -- older (2017), may need updating

---

## Metadata

**Confidence breakdown:**
- Erosion algorithms: HIGH -- peer-reviewed papers + working open source code inspected
- Noise libraries: HIGH -- packages verified on PyPI, opensimplex already installed
- Anti-jagging techniques: MEDIUM -- well-established in graphics but specific numpy implementations are custom
- Neural terrain: MEDIUM -- papers exist but no open pretrained weights readily available
- Performance estimates: MEDIUM -- based on algorithm complexity analysis, not benchmarked on VeilBreakers

**Research date:** 2026-04-02
**Valid until:** 2026-07-02 (stable domain -- erosion algorithms don't change fast; neural terrain moves faster)
