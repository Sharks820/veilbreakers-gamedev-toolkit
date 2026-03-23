# AI 3D Mesh Generation Techniques: Internal Architectures & Replicable Methods

**Researched:** 2026-03-22
**Domain:** Neural 3D generation internals -- mesh extraction, texturing, topology improvement
**Confidence:** HIGH (arxiv papers, official GitHub repos, verified implementations)
**Purpose:** Identify techniques from commercial/open-source AI mesh generators that can be replicated in our Blender Python toolkit for FREE

---

## Summary

Modern AI 3D mesh generators follow a remarkably consistent pipeline: (1) generate a neural 3D representation (triplane features, SDF field, or structured latents), (2) extract an explicit mesh from that representation (marching cubes, FlexiCubes, DMTet, or autoregressive face generation), (3) UV unwrap the mesh, and (4) generate PBR textures via multi-view diffusion + projection. Each stage contains techniques we can steal.

The most valuable techniques for VeilBreakers are NOT the neural network parts (which require massive training data and GPU compute). Instead, the replicable value lies in:

1. **SDF-based mesh generation** -- define shapes as math functions, extract meshes via marching cubes (pure Python, no ML)
2. **Multi-view texture projection** -- render views of a mesh, project textures back onto UVs to fill seams
3. **PBR channel estimation** -- predict roughness/metallic/normal from a single albedo using open-source models (CHORD)
4. **Curvature-based UV seam placement** -- algorithmic seam selection that hides cuts in high-curvature areas
5. **Non-uniform retopology weighting** -- more polygons on faces, fewer on body/feet

**Primary recommendation:** Implement SDF-based mesh generation as a new `blender_mesh` action (pure Python, zero dependencies beyond numpy), and integrate CHORD for PBR estimation from single images. These two techniques address the biggest gaps in our procedural mesh pipeline.

---

## How Each Tool Works Internally

### 1. Tripo3D (v3.0 / Smart Mesh P1.0)

**Architecture: Native 3D Diffusion on Probabilistic Space**

**Confidence: HIGH** (official blog, GDC 2026 presentation, multiple verified sources)

Tripo's latest architecture (P1.0, announced March 20 2026) represents a fundamental shift from earlier approaches:

**Shape Generation:**
- Uses a "unified probabilistic space" where the entire 3D mesh signal is probabilisticized
- Performs "global 3D geometric evolution" within this probability space
- Structural symmetry, proportional relationships, and geometric consistency arise naturally from the generation process itself, NOT from post-processing
- Trained on VAST's dataset of ~50 million high-quality 3D models that already adhere to industrial topology standards

**Mesh Extraction:**
- Earlier versions (v2.5) likely used triplane features + FlexiCubes/marching cubes (based on TRELLIS integration evidence)
- Smart Mesh P1.0 generates clean low-poly meshes directly -- polygon distribution is optimized during generation, not post-hoc
- The system builds a unified probability space and calculates structure before outputting geometry, rather than generating point-by-point into dense unstructured mesh

**Texture Generation:**
- PBR materials (albedo, normal, roughness, metallic) generated as separate channels in GLB
- Style transforms available (LEGO, voxel, cartoon, clay + custom)

**What We Can Steal:** Nothing from the neural architecture (requires 50M training models). But the CONCEPT of generating topology-aware meshes from probability fields inspires our SDF approach -- define the shape mathematically, extract clean mesh from it.

---

### 2. Meshy.ai (v4 / Meshy-6)

**Architecture: Triplane Latent Diffusion + SDF**

**Confidence: MEDIUM** (architecture inferred from similar published systems; Meshy has not published internal papers)

**Shape Generation:**
- Uses triplane latent diffusion similar to 3DGen architecture
- A triplane VAE learns latent representations of textured meshes
- A conditional diffusion model generates triplane features from text/image input
- SDF (Signed Distance Function) is the 3D shape representation

**Mesh Extraction:**
- Implicit SDF converted to explicit mesh via isosurface extraction (likely marching cubes or DMTet variant)
- Triangle-dominant output (not quad-focused)
- Auto-rigging and animation available as post-processing steps

**Texture Generation:**
- AI texturing as a separate stage after mesh generation
- PBR channel output
- Remesh operation available (5 credits)

**What We Can Steal:** The triplane concept is useful conceptually but requires ML training. The SDF-to-mesh-via-marching-cubes pipeline IS replicable without ML.

---

### 3. Hunyuan3D 2.1 (Open Source -- Most Replicable)

**Architecture: ShapeVAE + Flow-Matching DiT + Multi-View PBR Paint**

**Confidence: HIGH** (full arxiv paper, open-source code on GitHub, verified architecture)

**Shape Generation (Hunyuan3D-ShapeVAE):**

1. **Encoder** -- Converts polygon mesh to latent tokens:
   - Uses two-stage point sampling: uniform sampling + importance sampling on edges/corners
   - Farthest Point Sampling (FPS) generates point queries
   - Fourier positional encoding + linear projection
   - Cross-attention layers process queries against input point clouds
   - Produces mean/variance for variational bottleneck (latent dimension d0)
   - Variable token sequence length (max 3072 tokens)

2. **Decoder** -- Reconstructs mesh from tokens:
   - Transforms latent embeddings back to transformer width
   - Self-attention layers process hidden embeddings
   - Point perceiver queries a 3D grid (H x W x D) to obtain neural field features
   - Predicts **Signed Distance Function (SDF)** values via linear projection
   - Converts SDF to triangle mesh using **marching cubes algorithm**
   - Training uses MSE loss on SDF predictions + KL-divergence for latent regularization

3. **Flow-Matching Diffusion (Hunyuan3D-DiT):**
   - Forward process: x_t = (1-t) * x_0 + t * x_1
   - Velocity field: u_t = x_1 - x_0
   - Uses FLUX-inspired dual/single-stream architecture
   - First-order Euler ODE solver for inference

**Texture Generation (Hunyuan3D-Paint):**

- Multi-view PBR diffusion with dual-branch UNet
- Spatial-aligned multi-attention module aligns albedo and MR (metallic-roughness) maps
- 3D-aware Rotary Positional Embedding (RoPE) for cross-view consistency
- Illumination-invariant training: presents same mesh under different lighting, minimizes albedo consistency loss
- Geometry conditioning: concatenates canonical normal maps + coordinate maps with latent noise
- View selection: 4 fixed orthogonal + 4-8 iteratively selected views maximizing UV coverage
- Renders at 512x512, super-resolves, then bakes to UV via weighted vertex interpolation

**PolyGen (Quad Mesh Module):**

- Autoregressive face-by-face generation (NOT marching cubes)
- Uses BPT (Blocked and Patchified Tokenization) for 10K+ face meshes
- Learns quad topology end-to-end, producing continuous edge loops
- Reduces creation time by 70%, improves topology neatness by 35%
- NOTE: PolyGen weights may NOT be in the open-source release (requires validation)

**What We Can Steal:**

| Technique | Replicable? | How |
|-----------|-------------|-----|
| SDF prediction + marching cubes mesh extraction | YES (pure Python) | scipy/skimage marching_cubes on numpy SDF grids |
| Multi-view texture rendering + UV projection | YES (Blender Python) | Render from N views, project onto UVs |
| Illumination-invariant albedo (de-lighting) | YES (we already have `handle_delight`) | Enhance with CHORD model |
| View selection maximizing UV coverage | YES (geometry analysis) | Compute UV coverage per view, greedy select |
| Autoregressive quad generation | NO (requires trained model) | Use QuadriFlow instead |

---

### 4. Rodin Gen-2 (Hyper3D)

**Architecture: 10B Parameter BANG Architecture**

**Confidence: MEDIUM** (official API docs verified, internal architecture partially disclosed)

**Shape Generation:**
- 10 billion parameter model using "BANG architecture"
- Recursive part-based generation: deconstructs complex objects into constituent parts
- Generates each part with logical coherence, then assembles
- Produces clean quad-based meshes with fine surface detail directly

**Mesh Extraction:**
- Native quad mesh mode (up to 200K quad faces with edge flow)
- Raw triangular mode (up to 1M faces)
- Quality is the highest of any generator -- eliminates need for manual cleanup

**What We Can Steal:** The "recursive part-based generation" concept is brilliant for our procedural meshes. Instead of generating a sword as one object, generate pommel + guard + grip + blade separately with logical connections. We already do this partially in `procedural_meshes.py` but could formalize it.

---

### 5. TRELLIS.2 (Microsoft)

**Architecture: O-Voxel + Sparse Compression VAE + DiT**

**Confidence: HIGH** (MIT license, full code and paper available)

**O-Voxel Representation:**
- Novel sparse voxel structure encoding BOTH geometry and appearance
- Handles open surfaces, non-manifold geometry, enclosed interiors
- Breaks constraints of isosurface fields (not limited to watertight meshes)

**Compression:**
- Sparse 3D VAE with 16x spatial downsampling
- Encodes 1024^3 asset into only ~9.6K latent tokens
- Negligible perceptual degradation

**Mesh Extraction:**
- Instant Bidirectional Conversion between meshes and O-Voxel representation
- Supports arbitrary surface attributes: Base Color, Roughness, Metallic, Opacity

**What We Can Steal:** The sparse voxel approach aligns with Blender's OpenVDB integration. Blender 5.0+ has Grid to Mesh nodes using marching cubes on SDF grids. We can use OpenVDB-style operations for boolean combinations of SDF shapes.

---

### 6. SF3D (Stability AI)

**Architecture: Enhanced Triplane + Material Estimation + UV Unwrap**

**Confidence: HIGH** (open source, arxiv paper)

**5-Component Pipeline:**
1. Enhanced transformer predicting higher-resolution triplanes
2. Material estimation network predicting PBR properties
3. Illumination prediction for de-lighting
4. Mesh extraction with vertex offset prediction + surface normals
5. Fast UV unwrapping + export producing low-poly meshes with high-res textures

**Key Innovation:** Explicitly trained for mesh generation (not NeRF-to-mesh conversion). Integrates UV unwrapping INTO the generation pipeline rather than as post-processing.

**What We Can Steal:** The concept of predicting vertex offsets to refine mesh after initial extraction. We can add a vertex-offset smoothing pass after marching cubes extraction.

---

## Mesh Extraction Techniques (Detailed Comparison)

### Marching Cubes

**What:** Classic isosurface extraction from 3D scalar field (SDF volume). For each cube in a voxel grid, determines which of 256 possible surface configurations exists based on which corners are inside/outside the surface.

**Pros:**
- Simple to implement (scikit-image provides `measure.marching_cubes()`)
- Fast (linear in grid resolution)
- Produces watertight, manifold meshes
- Well-understood, stable algorithm

**Cons:**
- Fixed triangle patterns cause stair-step artifacts on non-axis-aligned features
- Cannot produce quad meshes
- Resolution is uniformly distributed (no detail where needed, waste elsewhere)
- Triangle count scales cubically with resolution (N^3)

**Implementation in Python:**
```python
import numpy as np
from skimage import measure

# Define SDF as 3D numpy array
grid_size = 128
x, y, z = np.mgrid[-1:1:grid_size*1j, -1:1:grid_size*1j, -1:1:grid_size*1j]

# Example: sphere SDF
sdf = np.sqrt(x**2 + y**2 + z**2) - 0.8

# Extract mesh
verts, faces, normals, values = measure.marching_cubes(sdf, level=0.0)

# Scale vertices to world coordinates
verts = verts / grid_size * 2 - 1
```

**Dependencies:** `numpy`, `scikit-image` (pip installable into Blender Python)

---

### DMTet (Deep Marching Tetrahedra)

**What:** Differentiable mesh extraction using tetrahedral grid. Converts implicit SDF to explicit mesh while allowing gradient backpropagation for optimization.

**Pros:**
- Differentiable (enables gradient-based optimization)
- Better feature preservation than marching cubes
- Tetrahedral grid at resolution N contains only (N/2+1)^3 vertices vs (N+1)^3 for voxel grids

**Cons:**
- Produces many sliver triangles
- Requires PyTorch + CUDA
- More complex implementation
- NOT suitable for pure-Python Blender addon

**Verdict:** Not implementable in our Blender addon without heavy dependencies. Skip.

---

### FlexiCubes (NVIDIA)

**What:** Flexible isosurface extraction designed for gradient-based mesh optimization. Builds on Dual Marching Cubes with additional weight parameters for local mesh geometry and connectivity adjustment.

**Pros:**
- More uniform tessellation than DMTet
- Faithfully captures small geometric details
- Manifold and watertight output
- Simplifies UV unwrapping
- NVIDIA integrates as drop-in DMTet replacement

**Cons:**
- Requires PyTorch, CUDA, Kaolin (v0.15.0+), nvdiffrast
- Designed for optimization (not standalone extraction)
- Heavy dependency chain

**Verdict:** Too many dependencies for Blender addon. The CONCEPT of flexible vertex positioning within dual cells is interesting -- we could implement a simplified version as a post-marching-cubes vertex relaxation step.

---

### Autoregressive Face Generation (PolyGen / Hunyuan3D-PolyGen)

**What:** Generates mesh faces one at a time using a transformer model. Each face is predicted conditioned on previously generated faces.

**Pros:**
- Produces quad-dominant topology with proper edge flow
- Learns topology patterns from training data
- Can generate animation-ready meshes directly

**Cons:**
- Requires trained transformer model (billions of parameters)
- Cannot be implemented without ML training infrastructure
- Slow (sequential face generation)

**Verdict:** Cannot replicate without training. Use QuadriFlow (already in Blender) instead.

---

### Recommendation for VeilBreakers

**Use marching cubes via scikit-image.** It is the only extraction method implementable in pure Python within Blender's constraints. The quality limitations (stair-stepping, triangle-only) are addressed by our existing post-processing pipeline: marching cubes output -> voxel remesh for cleanup -> QuadriFlow for quad topology -> UV unwrap -> PBR texturing.

---

## Texture Generation Techniques

### Multi-View Texture Projection

**How Commercial Tools Do It:**
1. Render the mesh from 8-12 viewpoints (selected to maximize UV coverage)
2. Generate/modify images for each viewpoint using AI (diffusion models)
3. Project each view's pixels back onto the mesh UV map
4. Blend overlapping projections (weighted by view angle to surface normal)
5. Inpaint remaining holes using spatial-aware 3D inpainting

**Replicable in Blender Python: YES**

**Implementation approach:**
```python
# Pseudocode for multi-view texture projection in Blender
import bpy
import mathutils

def project_views_to_texture(obj, views, texture_size=2048):
    """
    1. For each view:
       a. Set camera to view position/rotation
       b. Render the scene (or use a reference texture)
       c. For each UV face:
          - Check if face normal faces the camera (dot product > threshold)
          - If visible, sample the rendered image at projected UV coordinates
          - Write pixel to texture with weight = dot(face_normal, view_dir)
    2. Normalize by total weights
    3. Inpaint remaining zero-weight pixels using nearest-neighbor diffusion
    """
    pass
```

**Blender APIs needed:**
- `bpy.ops.render.render()` for rendering views
- `bpy.types.Image` for texture creation/manipulation
- `mathutils.geometry.intersect_ray_tri()` for visibility checks
- Camera projection matrix via `bpy_extras.object_utils.world_to_camera_view()`

**Key insight from MVPaint (CVPR 2025):** The Spatial-aware Seam-Smoothing Algorithm (SSA) repairs UV seams by computing a weighted sum of textures from connected textured vertices, with weights as reciprocal of geometric distances. This is implementable in pure Python as a post-processing pass on the UV texture.

---

### PBR Channel Estimation from Single Image

**How Commercial Tools Do It:**

Most generators predict PBR channels (albedo, normal, roughness, metallic) using neural networks trained on large material datasets. The state-of-the-art approach is CHORD (Ubisoft LaForge, SIGGRAPH Asia 2025).

**CHORD Pipeline (Open Source!):**

1. **Base Color Prediction:** Predicts clean albedo first (removing baked lighting)
2. **Irradiance Estimation:** Computes approximated irradiance by removing color from input
3. **Normal Map Prediction:** Uses irradiance map to predict surface normals
4. **Height/Roughness/Metalness:** Cascaded prediction using chain of rendering decomposition

**Available:** Open-source weights on GitHub (`ubisoft/ubisoft-laforge-chord`) and HuggingFace. ComfyUI nodes available. Licensed under Ubisoft Machine Learning License (Research-Only - Copyleft).

**Integration approach for VeilBreakers:**
- Install CHORD model weights (~2GB)
- Create `chord_client.py` wrapper similar to `tripo_client.py`
- Input: single albedo/color texture image
- Output: normal map, height map, roughness map, metalness map
- Feed outputs into `blender_texture create_pbr` node tree

**Fallback (no ML required):** Simple heuristic PBR estimation:
```python
def estimate_pbr_from_albedo(albedo_image):
    """
    Heuristic PBR estimation without neural networks.

    Roughness: inverse of local contrast (smooth = low contrast, rough = high)
    Metallic: saturation-based (highly saturated = non-metallic, desaturated = metallic)
    Normal: derived from albedo luminance gradient (Sobel filter)
    AO: dark areas in albedo suggest occlusion
    """
    import numpy as np

    # Roughness from local variance
    kernel_size = 8
    local_var = sliding_window_variance(albedo, kernel_size)
    roughness = 1.0 - np.clip(local_var * 10, 0, 1)

    # Metallic from desaturation
    hsv = rgb_to_hsv(albedo)
    metallic = 1.0 - hsv[:,:,1]  # Low saturation = metallic
    metallic = np.clip(metallic - 0.3, 0, 1)  # Threshold

    # Normal from luminance gradient
    gray = np.mean(albedo, axis=2)
    dx = sobel_x(gray)
    dy = sobel_y(gray)
    normal_map = np.stack([dx, dy, np.ones_like(dx)], axis=2)
    normal_map = normalize(normal_map)

    return roughness, metallic, normal_map
```

---

### Albedo De-lighting

**How Commercial Tools Do It:**

- SF3D: learns to predict low-frequency illumination, subtracts it from albedo
- Hunyuan3D-Paint: illumination-invariant training -- presents same mesh under different lighting, forces consistent albedo prediction
- IDArb: takes arbitrary images under varying lighting, predicts intrinsic components

**Current VeilBreakers Status:** We already have `handle_delight` in `blender_texture`. The technique works by:
1. Converting to LAB color space
2. Applying low-pass filter to L channel to estimate lighting
3. Dividing original L by estimated lighting
4. Clamping and converting back

**Enhancement opportunity:** Integrate CHORD's base-color prediction for better de-lighting than our current frequency-based approach.

---

## Topology Improvement Techniques

### QuadriFlow (Already in Blender)

**How it works:** Field-aligned quad meshing using maximum flow solver. Takes manifold triangle input, outputs manifold quad mesh. Edge flow follows geometry curvature but NOT anatomical features.

**Limitation for game characters:** Topology follows flow of geometry but cannot enforce edge loops around eyes, mouth, elbows, knees. This requires either:
1. Manual guidance (marking feature edges)
2. Anatomically-aware retopology (ML-based)

**What we use now:** `blender_mesh retopo` action calls QuadriFlow via `bpy.ops.object.quadriflow_remesh()`.

---

### Instant Meshes Algorithm

**How it works:** Field-aligned isotropic triangular or quad-dominant meshing. Uses a unified local smoothing operator to optimize edge orientations and vertex positions. Naturally aligns and snaps edges to sharp features.

**Implementation:** C++ with no Python bindings. Integrated into Modo since v10.2. NOT directly callable from Blender Python.

**Alternative in Blender:** Blender's voxel remesher + QuadriFlow provides similar (though not identical) results.

---

### Face-Aware Retopology (Non-Uniform Density)

**The Problem:** QuadriFlow and Instant Meshes distribute polygons uniformly. Game characters need MORE polygons on faces (for expressions) and FEWER on bodies/feet.

**How AAA Studios Do It:**
1. Create a "density map" (vertex color or weight paint) marking high-detail zones
2. Retopologize with density weighting
3. Face region: 4x density multiplier
4. Hands: 2x density multiplier
5. Feet/back: 0.5x density multiplier

**Implementable in Blender Python: YES**

**Approach:**
```python
def face_aware_retopo(obj, target_faces=10000):
    """
    1. Detect face region (by vertex group 'Head' or by bounding box heuristic)
    2. Separate face region from body
    3. Retopo face at high density (target_faces * 0.3 for face alone)
    4. Retopo body at low density (target_faces * 0.7 for rest)
    5. Rejoin and merge border vertices
    """
    # Detect head region
    head_verts = detect_head_region(obj)  # top 15% of bounding box height

    # Separate into head and body meshes
    head_obj, body_obj = separate_by_vertices(obj, head_verts)

    # Retopo each at different density
    retopo(head_obj, target_faces=int(target_faces * 0.3))
    retopo(body_obj, target_faces=int(target_faces * 0.7))

    # Rejoin
    join_meshes(head_obj, body_obj)
```

---

### Curvature-Based UV Seam Placement

**How it works:** Instead of placing UV seams arbitrarily, analyze mesh curvature and place seams along high-curvature edges (sharp creases, natural material boundaries) where texture discontinuities are least noticeable.

**Open-source implementations:**
- OKUnwrap (Blender addon): curvature-based automatic UV seam placement
- UVgami: advanced single-click UV unwrapping

**Implementable in Blender Python: YES**

**Approach:**
```python
def curvature_based_seams(obj):
    """
    1. Calculate edge dihedral angles (angle between adjacent face normals)
    2. Sort edges by dihedral angle (highest = sharpest crease)
    3. Mark top N% as UV seams
    4. Ensure seam graph is connected (flood fill to verify UV islands)
    5. Add minimal seams to connect disconnected islands
    """
    import bmesh
    bm = bmesh.from_edit_mesh(obj.data)

    edge_angles = []
    for edge in bm.edges:
        if len(edge.link_faces) == 2:
            angle = edge.link_faces[0].normal.angle(edge.link_faces[1].normal)
            edge_angles.append((edge, angle))

    # Sort by angle descending
    edge_angles.sort(key=lambda x: x[1], reverse=True)

    # Mark top 20% as seams
    cutoff = int(len(edge_angles) * 0.2)
    for edge, angle in edge_angles[:cutoff]:
        edge.seam = True
```

---

## SDF-Based Mesh Generation for VeilBreakers

This is the highest-value technique to implement. Instead of assembling primitives via bmesh (our current approach in `procedural_meshes.py`), define shapes as mathematical SDF functions and extract meshes via marching cubes.

### Why SDF is Better Than Our Current Approach

| Aspect | Current (bmesh primitives) | SDF + Marching Cubes |
|--------|---------------------------|---------------------|
| Boolean operations | Complex bmesh boolean (often fails) | Simple min/max on scalar fields |
| Smooth blending | Not possible | smooth_union/smooth_subtract functions |
| Organic shapes | Very difficult | Natural with noise-modulated SDFs |
| Detail control | Manual vertex placement | Resolution-based (increase grid = more detail) |
| Reliability | Boolean ops crash on edge cases | Always produces valid mesh |

### SDF Primitives Library

```python
import numpy as np

def sdf_sphere(p, center, radius):
    """Signed distance to sphere."""
    return np.linalg.norm(p - center, axis=-1) - radius

def sdf_box(p, center, half_extents):
    """Signed distance to axis-aligned box."""
    q = np.abs(p - center) - half_extents
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(np.max(q, axis=-1), 0)

def sdf_cylinder(p, center, radius, half_height, axis='z'):
    """Signed distance to cylinder."""
    axes = {'x': 0, 'y': 1, 'z': 2}
    ax = axes[axis]
    radial = np.delete(p - center, ax, axis=-1)
    d_radial = np.linalg.norm(radial, axis=-1) - radius
    d_height = np.abs((p - center)[..., ax]) - half_height
    return np.maximum(d_radial, d_height)

def sdf_torus(p, center, major_radius, minor_radius):
    """Signed distance to torus (XY plane)."""
    q = p - center
    xz = np.sqrt(q[..., 0]**2 + q[..., 1]**2) - major_radius
    return np.sqrt(xz**2 + q[..., 2]**2) - minor_radius

def sdf_capsule(p, a, b, radius):
    """Signed distance to capsule (line segment a-b with radius)."""
    pa = p - a
    ba = b - a
    h = np.clip(np.sum(pa * ba, axis=-1) / np.sum(ba * ba), 0, 1)
    return np.linalg.norm(pa - h[..., np.newaxis] * ba, axis=-1) - radius

# --- Boolean Operations ---

def sdf_union(d1, d2):
    return np.minimum(d1, d2)

def sdf_intersection(d1, d2):
    return np.maximum(d1, d2)

def sdf_difference(d1, d2):
    return np.maximum(d1, -d2)

def sdf_smooth_union(d1, d2, k=0.1):
    """Smooth minimum for organic blending."""
    h = np.clip(0.5 + 0.5 * (d2 - d1) / k, 0, 1)
    return d2 * (1 - h) + d1 * h - k * h * (1 - h)

def sdf_smooth_difference(d1, d2, k=0.1):
    """Smooth subtraction."""
    return sdf_smooth_union(d1, -d2, k)

# --- Transforms ---

def sdf_translate(sdf_func, offset):
    def f(p): return sdf_func(p - offset)
    return f

def sdf_scale(sdf_func, scale):
    def f(p): return sdf_func(p / scale) * scale
    return f

def sdf_rotate_z(sdf_func, angle):
    c, s = np.cos(angle), np.sin(angle)
    def f(p):
        rotated = p.copy()
        rotated[..., 0] = c * p[..., 0] - s * p[..., 1]
        rotated[..., 1] = s * p[..., 0] + c * p[..., 1]
        return sdf_func(rotated)
    return f

# --- Deformations ---

def sdf_twist(sdf_func, twist_rate):
    """Twist shape around Z axis."""
    def f(p):
        angle = p[..., 2] * twist_rate
        c, s = np.cos(angle), np.sin(angle)
        twisted = p.copy()
        twisted[..., 0] = c * p[..., 0] - s * p[..., 1]
        twisted[..., 1] = s * p[..., 0] + c * p[..., 1]
        return sdf_func(twisted)
    return f

def sdf_bend(sdf_func, bend_amount):
    """Bend shape along Z axis."""
    def f(p):
        angle = p[..., 2] * bend_amount
        c, s = np.cos(angle), np.sin(angle)
        bent = p.copy()
        bent[..., 0] = c * p[..., 0] - s * p[..., 2]
        bent[..., 2] = s * p[..., 0] + c * p[..., 2]
        return sdf_func(bent)
    return f

# --- Noise for Organic Detail ---

def sdf_displace(sdf_func, noise_func, amplitude=0.05):
    """Add noise displacement to SDF surface."""
    def f(p):
        return sdf_func(p) + noise_func(p) * amplitude
    return f
```

### Mesh Extraction Pipeline

```python
from skimage import measure

def sdf_to_mesh(sdf_func, bounds=(-1, 1), resolution=128):
    """
    Convert SDF function to mesh vertices and faces.

    Args:
        sdf_func: function taking (N, 3) array, returning (N,) distances
        bounds: (min, max) for sampling grid
        resolution: grid resolution per axis

    Returns:
        vertices: (V, 3) array
        faces: (F, 3) array of vertex indices
        normals: (V, 3) array
    """
    # Create 3D grid
    lin = np.linspace(bounds[0], bounds[1], resolution)
    x, y, z = np.meshgrid(lin, lin, lin, indexing='ij')
    points = np.stack([x, y, z], axis=-1)

    # Evaluate SDF on grid
    sdf_values = sdf_func(points.reshape(-1, 3)).reshape(resolution, resolution, resolution)

    # Extract mesh via marching cubes
    verts, faces, normals, _ = measure.marching_cubes(sdf_values, level=0.0)

    # Scale vertices to world coordinates
    scale = (bounds[1] - bounds[0]) / resolution
    verts = verts * scale + bounds[0]

    return verts, faces, normals

def sdf_mesh_to_blender(name, sdf_func, resolution=128, bounds=(-1, 1)):
    """
    Generate mesh from SDF and create Blender object.
    Runs inside Blender Python context.
    """
    import bpy
    import bmesh

    verts, faces, normals = sdf_to_mesh(sdf_func, bounds, resolution)

    # Create mesh data
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts.tolist(), [], faces.tolist())
    mesh.update()

    # Create object
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)

    return obj
```

### Example: SDF-Based Potion Bottle

```python
def potion_bottle(p):
    """Dark fantasy potion bottle via SDF composition."""
    # Body: elongated sphere
    body = sdf_sphere(p, [0, 0, 0], 0.3)
    body = np.minimum(body, sdf_sphere(p, [0, 0, 0.1], 0.28))

    # Neck: cylinder
    neck = sdf_cylinder(p, [0, 0, 0.4], 0.08, 0.15, axis='z')

    # Rim: torus
    rim = sdf_torus(p, [0, 0, 0.55], 0.1, 0.02)

    # Combine with smooth union
    result = sdf_smooth_union(body, neck, k=0.05)
    result = sdf_smooth_union(result, rim, k=0.02)

    # Bottom: slight flat
    flat = sdf_box(p, [0, 0, -0.35], [0.5, 0.5, 0.05])
    result = sdf_difference(result, flat)

    return result
```

### Dependencies and Installation

For the Blender addon, we need `numpy` (already available in Blender) and `scikit-image` (needs pip install into Blender Python). Alternative: use a simplified marching cubes implementation in pure numpy that doesn't require scikit-image.

**Pure-numpy marching cubes fallback:** The algorithm is well-documented enough to implement a simplified version (~200 lines of Python using the 256-entry lookup table). This avoids the scikit-image dependency entirely.

---

## Blender OpenVDB Integration (Alternative to scikit-image)

Blender 5.0+ ships with OpenVDB and exposes volume operations through Geometry Nodes:

- **Mesh to Volume:** Convert mesh to SDF volume grid
- **Volume to Mesh (Grid to Mesh):** Extract isosurface using marching cubes
- **Volume Boolean:** Union/intersection/difference on SDF volumes
- **SDF Filters:** Smoothing, dilation, erosion on SDF grids

**Python access:** OpenVDB grids are C++ data structures. Direct Python API is limited, but we CAN:
1. Create a mesh primitive
2. Add a "Mesh to Volume" modifier
3. Add boolean modifiers operating on volumes
4. Add a "Volume to Mesh" modifier
5. Apply modifiers to get result

**This is MORE reliable than bmesh booleans** because SDF boolean operations are mathematically well-defined and don't suffer from the edge-case failures that plague mesh booleans.

---

## What We Can Implement for FREE (Prioritized)

### Tier 1: High Value, Pure Python (No ML)

| # | Technique | Implementation | Effort | Value |
|---|-----------|---------------|--------|-------|
| 1 | **SDF mesh generation** | numpy + marching cubes (skimage or pure numpy) | MEDIUM | CRITICAL -- replaces bmesh booleans with reliable SDF booleans, enables organic shapes |
| 2 | **Curvature-based UV seams** | bmesh edge analysis, dihedral angle sorting | LOW | HIGH -- better UV layouts for all generated meshes |
| 3 | **Face-aware retopology** | Separate head/body, retopo at different densities | MEDIUM | HIGH -- character meshes need non-uniform density |
| 4 | **Multi-view texture projection** | Blender render + UV projection | MEDIUM | HIGH -- fill texture seams, create textures from renders |
| 5 | **SDF smooth booleans** | sdf_smooth_union/difference functions | LOW | HIGH -- organic mesh blending impossible with bmesh |
| 6 | **Heuristic PBR estimation** | numpy image processing (variance, saturation, Sobel) | LOW | MEDIUM -- quick PBR from single albedo |
| 7 | **Vertex-offset smoothing** | Post-marching-cubes vertex relaxation | LOW | MEDIUM -- reduces stair-stepping artifacts |
| 8 | **Part-based mesh assembly** | Formalize component-based generation (Rodin concept) | LOW | MEDIUM -- cleaner procedural meshes |

### Tier 2: With Local AI Models

| # | Technique | Model | VRAM | Effort | Value |
|---|-----------|-------|------|--------|-------|
| 9 | **PBR from single image (CHORD)** | Ubisoft CHORD | ~4GB | MEDIUM | HIGH -- production-quality PBR estimation |
| 10 | **Hunyuan3D self-hosted** | Hunyuan3D 2.1 | 6GB+ | HIGH | HIGH -- free text/image-to-3D |
| 11 | **Enhanced de-lighting** | IDArb or CHORD base-color | ~4GB | MEDIUM | MEDIUM -- better than our current LAB approach |

### Tier 3: Blender Built-in (No Code Needed)

| # | Technique | Blender Feature | Effort | Value |
|---|-----------|----------------|--------|-------|
| 12 | **OpenVDB SDF booleans** | Geometry Nodes (Blender 5.0+) | LOW | HIGH -- if target Blender version supports it |
| 13 | **Voxel remesh cleanup** | Remesh modifier (voxel mode) | ZERO | MEDIUM -- already available, just needs better parameterization |

---

## Implementation Priority for VeilBreakers

### Phase 1: SDF Foundation (Unlocks Organic Meshes)

**Goal:** Add `blender_mesh` action `sdf_generate` that creates meshes from SDF function definitions.

**Implementation:**
1. Create `sdf_library.py` in `blender_addon/handlers/` with SDF primitives + booleans
2. Add marching cubes extraction (pure numpy implementation or scikit-image)
3. Wire into `handle_sdf_generate()` that accepts SDF composition as JSON
4. Post-processing: auto-apply voxel remesh + QuadriFlow + smooth normals

**Blender APIs:**
- `bpy.data.meshes.new()` / `mesh.from_pydata()` for mesh creation
- `bpy.ops.object.modifier_add(type='REMESH')` for cleanup
- `bpy.ops.object.quadriflow_remesh()` for quad retopo

**JSON interface example:**
```json
{
  "action": "sdf_generate",
  "name": "dark_potion",
  "resolution": 128,
  "primitives": [
    {"type": "sphere", "center": [0,0,0], "radius": 0.3},
    {"type": "cylinder", "center": [0,0,0.4], "radius": 0.08, "height": 0.3},
    {"type": "torus", "center": [0,0,0.55], "major": 0.1, "minor": 0.02}
  ],
  "operations": [
    {"op": "smooth_union", "a": 0, "b": 1, "k": 0.05},
    {"op": "smooth_union", "a": "result", "b": 2, "k": 0.02}
  ],
  "post_process": {
    "remesh_voxel_size": 0.01,
    "quadriflow_faces": 2000,
    "smooth_iterations": 2
  }
}
```

### Phase 2: Enhanced Texturing

**Goal:** Add multi-view texture projection and PBR estimation.

1. `blender_texture` action `project_views` -- render from N angles, project to UV
2. `blender_texture` action `estimate_pbr` -- heuristic PBR from albedo (no ML)
3. Optional: integrate CHORD model for production PBR estimation

### Phase 3: Smart Retopology

**Goal:** Face-aware non-uniform retopology for characters.

1. `blender_mesh` action `retopo_weighted` -- density map input, variable poly distribution
2. `blender_uv` action `auto_seams` -- curvature-based seam placement

---

## Common Pitfalls When Implementing These Techniques

### Pitfall 1: Marching Cubes Resolution vs. Performance
**What goes wrong:** Setting grid resolution too high (256+) causes memory exhaustion and multi-minute generation times.
**Why it happens:** Memory scales as O(N^3). 256^3 = 16.7M voxels * 4 bytes = 67MB just for the SDF. Marching cubes lookup adds more.
**How to avoid:** Default to 128 (2M voxels), allow up to 256 for hero assets. Profile memory before increasing.
**Warning signs:** Blender freezing during mesh generation.

### Pitfall 2: SDF Boolean Artifacts at Thin Features
**What goes wrong:** Smooth union with high k value (>0.1) swallows thin features like sword blades.
**Why it happens:** Smooth min function blends over a radius of k. If feature width < 2k, it gets smoothed away.
**How to avoid:** Use k=0.01-0.03 for sharp features, k=0.05-0.1 only for organic blending.
**Warning signs:** Features disappearing or becoming bulbous at intersection points.

### Pitfall 3: UV Projection Stretch at Grazing Angles
**What goes wrong:** Multi-view texture projection produces stretched/blurry textures on faces nearly parallel to camera view.
**Why it happens:** A face at 80+ degrees to the camera view direction covers many mesh pixels but few image pixels.
**How to avoid:** Weight contributions by cos(angle) between face normal and view direction. Discard contributions below cos(75 degrees).
**Warning signs:** Blurry streaks on sides of objects, texture stretching on curves.

### Pitfall 4: scikit-image Dependency in Blender
**What goes wrong:** `import skimage` fails because Blender ships its own Python without scientific packages.
**Why it happens:** Blender's Python environment is isolated from system Python.
**How to avoid:** Either: (a) pip install scikit-image into Blender's Python at addon install time, or (b) implement simplified marching cubes in pure numpy (preferred -- no external dependency).
**Warning signs:** ImportError on first run.

### Pitfall 5: Heuristic PBR Estimation Quality
**What goes wrong:** Variance-based roughness estimation produces noisy, unrealistic material maps.
**Why it happens:** Simple heuristics cannot capture complex material relationships (e.g., wet stone vs dry metal).
**How to avoid:** Use heuristic PBR ONLY as fallback. Prefer CHORD when available. Always provide manual override parameters.
**Warning signs:** Materials looking uniformly rough or uniformly metallic.

---

## State of the Art (What Changed in 2025-2026)

| Old Approach (2024) | Current Approach (2026) | Impact on Our Toolkit |
|---------------------|------------------------|----------------------|
| NeRF-to-mesh via marching cubes | Native 3D diffusion (Tripo P1.0) | No change -- we still use marching cubes for SDF extraction |
| Random triangle topology | Quad-dominant autoregressive (PolyGen) | Use QuadriFlow as approximation |
| Baked lighting in albedo | Illumination-invariant training | Enhance our delight pipeline with CHORD |
| Single-view texturing | Multi-view 8-12 angle projection + inpainting | Implement multi-view projection in Blender |
| Manual PBR authoring | AI PBR estimation (CHORD, SuperMat) | Integrate CHORD for auto-PBR from albedo |
| Post-hoc UV unwrapping | Generation-integrated UV (SF3D) | Curvature-based auto-seams before unwrap |
| Uniform retopology | Face-aware density distribution | Implement weighted retopology |

---

## Open Questions

1. **scikit-image vs pure numpy marching cubes**
   - What we know: scikit-image provides battle-tested marching cubes implementation
   - What's unclear: Whether pip install into Blender Python works reliably across platforms
   - Recommendation: Implement both -- pure numpy fallback, scikit-image when available

2. **Blender 5.0 OpenVDB volume nodes via Python API**
   - What we know: Geometry Nodes have 27 new volume nodes including mesh-to-SDF and SDF booleans
   - What's unclear: Whether these can be driven programmatically via bpy Python API (they're normally GUI-only)
   - Recommendation: Test if `bpy.ops.node.add_node()` can build geometry node trees programmatically

3. **CHORD license compatibility**
   - What we know: Ubisoft Machine Learning License (Research-Only - Copyleft)
   - What's unclear: Whether "research-only" blocks use in a game dev toolkit
   - Recommendation: Use for internal tooling, not distribution. Fall back to heuristic PBR for distribution.

4. **Hunyuan3D-PolyGen open source status**
   - What we know: PolyGen announced July 2025 with autoregressive quad mesh generation
   - What's unclear: Whether model weights are included in the GitHub release
   - Recommendation: Check `github.com/Tencent-Hunyuan/Hunyuan3D-2.1/releases` for PolyGen weights

---

## Sources

### Primary (HIGH confidence)
- [Hunyuan3D 2.0 Paper (arxiv 2501.12202)](https://arxiv.org/html/2501.12202v1) -- ShapeVAE architecture, flow matching, marching cubes decoder
- [Hunyuan3D 2.1 Paper (arxiv 2506.15442)](https://arxiv.org/html/2506.15442v1) -- PBR Paint module, illumination-invariant training
- [FlexiCubes GitHub (NVIDIA)](https://github.com/nv-tlabs/FlexiCubes) -- Differentiable mesh extraction
- [FlexiCubes Research Page](https://research.nvidia.com/labs/toronto-ai/flexicubes/) -- Comparison with marching cubes and DMTet
- [scikit-image Marching Cubes](https://scikit-image.org/docs/stable/auto_examples/edges/plot_marching_cubes.html) -- Python implementation
- [fogleman/sdf GitHub](https://github.com/fogleman/sdf) -- Pure Python SDF mesh generation library
- [CHORD GitHub (Ubisoft)](https://github.com/ubisoft/ubisoft-laforge-chord) -- Open-source PBR estimation
- [SF3D GitHub (Stability AI)](https://github.com/Stability-AI/stable-fast-3d) -- UV unwrap + de-lighting architecture
- [TRELLIS.2 GitHub (Microsoft)](https://github.com/microsoft/TRELLIS.2) -- O-Voxel architecture, MIT license
- [Blender Volume Grids Blog](https://code.blender.org/2025/10/volume-grids-in-geometry-nodes/) -- OpenVDB in Geometry Nodes
- [Blender Grid to Mesh Node](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/volume/operations/grid_to_mesh.html) -- Marching cubes in Blender

### Secondary (MEDIUM confidence)
- [Tripo Smart Mesh P1.0 Blog](https://www.tripo3d.ai/blog/introducing-smart-mesh-v1) -- Architecture description
- [Tripo P1.0 Analysis (Medium)](https://medium.com/data-science-in-your-pocket/tripo-smart-mesh-p1-0-generating-clean-low-poly-3d-meshes-in-just-2-seconds-03bc1b260b28) -- Technical breakdown
- [Rodin Gen-2 API Docs](https://developer.hyper3d.ai/api-specification/rodin-generation-gen2) -- BANG architecture mention
- [MVPaint (CVPR 2025)](https://mvpaint.github.io/) -- Multi-view texture projection with SSA
- [CHORD Ubisoft Blog](https://www.ubisoft.com/en-us/studio/laforge/news/1i3YOvQX2iArLlScBPqBZs/) -- PBR estimation pipeline
- [Hunyuan3D-PolyGen Announcement](https://www.artificialintelligence-news.com/news/tencent-hunyuan3d-polygen-a-model-for-art-grade-3d-assets/) -- Autoregressive quad mesh
- [mesh-to-sdf PyPI](https://pypi.org/project/mesh-to-sdf/) -- Python SDF computation library
- [Instant Meshes GitHub](https://github.com/wjakob/instant-meshes) -- Quad remeshing algorithm

### Tertiary (LOW confidence)
- [IDArb Intrinsic Decomposition](https://arxiv.org/html/2412.12083v3) -- Multi-view material estimation
- [OKUnwrap Blender Addon](https://github.com/Eritar/okunwrap-blender) -- Curvature-based UV seams
- Meshy internal architecture -- inferred from similar published systems, not officially disclosed

---

## Metadata

**Confidence breakdown:**
- SDF mesh generation technique: HIGH -- well-documented algorithm, multiple implementations
- Marching cubes in Python: HIGH -- scikit-image official docs + pure numpy feasible
- Commercial tool architectures (Tripo, Meshy, Rodin): MEDIUM -- some details inferred
- Hunyuan3D internals: HIGH -- full arxiv paper + open source code
- TRELLIS.2 internals: HIGH -- MIT license, full code available
- PBR estimation (CHORD): HIGH -- open source with paper
- Texture projection technique: MEDIUM -- based on MVPaint paper + Blender API docs
- Face-aware retopology: MEDIUM -- concept validated but custom implementation needed

**Research date:** 2026-03-22
**Valid until:** 2026-05-22 (60 days -- fundamental algorithms don't change fast)
