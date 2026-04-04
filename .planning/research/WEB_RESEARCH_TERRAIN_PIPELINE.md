# Web Research Pipeline for Terrain Generation

**Domain:** Automated reference-driven terrain generation for dark fantasy game assets
**Researched:** 2026-04-03
**Overall Confidence:** MEDIUM-HIGH (architecture is novel integration of proven components)

---

## 1. Image Reference Lookup for Terrain Generation

### APIs for Reference Images

**Use Pexels API** because it is completely free with no attribution required for the use case (internal tooling), has a simple REST API, and returns high-quality landscape/terrain photos.

| API | Rate Limit | Cost | Best For |
|-----|-----------|------|----------|
| **Pexels** (recommended) | 200/hr, 20K/month | Free | Terrain reference images, no auth complexity |
| Unsplash | 1000/hr | Free | Higher volume, but requires attribution |
| Google Custom Search | 100/day free | $5/1K after | Broader results, lower quality filtering |

**Implementation pattern:**

```python
import httpx

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

async def fetch_terrain_references(
    biome_query: str,
    count: int = 5,
    orientation: str = "landscape",
) -> list[dict]:
    """Fetch reference images from Pexels for a biome description.

    Returns list of dicts with keys: url, width, height, photographer.
    """
    headers = {"Authorization": PEXELS_API_KEY}
    params = {
        "query": f"{biome_query} terrain landscape nature",
        "per_page": count,
        "orientation": orientation,
        "size": "medium",  # 350x350 to 2000x2000 -- enough for color extraction
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
    return [
        {
            "url": photo["src"]["medium"],
            "original_url": photo["src"]["original"],
            "width": photo["width"],
            "height": photo["height"],
            "photographer": photo["photographer"],
        }
        for photo in data.get("photos", [])
    ]
```

**Query construction for biome types:**

| Biome | Search Query |
|-------|-------------|
| thornwood_forest | `"dark dense forest floor moss roots"` |
| corrupted_swamp | `"dark swamp murky water dead trees"` |
| mountain_pass | `"mountain pass rocky terrain alpine"` |
| ruined_fortress | `"ruined castle stone rubble medieval"` |
| veil_crack_zone | `"volcanic cracked earth lava glow"` |
| cemetery | `"old cemetery foggy dark gravestones"` |
| mushroom_forest | `"bioluminescent mushroom forest glow"` |

### Color Palette Extraction

**Use scikit-learn KMeans clustering** because it is already available in Python, battle-tested, and produces exactly the output needed (dominant RGB centroids that map directly to `base_color` tuples).

Do NOT use Pylette or colorgram.py -- they add unnecessary dependencies for what is a 20-line function with sklearn.

```python
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

def extract_terrain_palette(
    image_path: str,
    n_colors: int = 6,
    resize_to: int = 200,
) -> list[tuple[float, float, float, float]]:
    """Extract dominant colors from a terrain reference image.

    Returns colors as (R, G, B, A) tuples normalized to 0.0-1.0
    for direct use in BIOME_PALETTES_V2 base_color fields.

    Colors are sorted dark-to-light (typical terrain layering:
    ground=darkest, cliff=medium, special=lightest/most saturated).
    """
    img = Image.open(image_path).convert("RGB")
    # Resize for performance -- 200px is enough for color extraction
    ratio = resize_to / max(img.size)
    img = img.resize((int(img.size[0] * ratio), int(img.size[1] * ratio)))

    pixels = np.array(img).reshape(-1, 3).astype(float) / 255.0
    kmeans = KMeans(n_clusters=n_colors, n_init=10, random_state=42)
    kmeans.fit(pixels)

    # Sort by luminance (dark to light)
    centers = kmeans.cluster_centers_
    luminance = 0.299 * centers[:, 0] + 0.587 * centers[:, 1] + 0.114 * centers[:, 2]
    sorted_idx = np.argsort(luminance)
    colors = centers[sorted_idx]

    return [(float(r), float(g), float(b), 1.0) for r, g, b in colors]
```

**Dark fantasy palette enforcement:** After extraction, apply the VeilBreakers saturation/value rules:
- Environment saturation NEVER exceeds 40%
- Value range for environments: 10-50% (dark world)

```python
import colorsys

def enforce_dark_fantasy_palette(
    colors: list[tuple[float, float, float, float]],
    max_saturation: float = 0.40,
    max_value: float = 0.50,
    min_value: float = 0.10,
) -> list[tuple[float, float, float, float]]:
    """Clamp extracted colors to VeilBreakers dark fantasy range."""
    result = []
    for r, g, b, a in colors:
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        s = min(s, max_saturation)
        v = max(min_value, min(v, max_value))
        r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
        result.append((round(r2, 3), round(g2, 3), round(b2, 3), a))
    return result
```

### Texture Pattern Analysis with zai Tools

The `analyze_image` zai MCP tool can extract semantic terrain information from reference photos. Use it to identify:

- Vegetation density (sparse vs dense)
- Rock exposure percentage
- Water presence and type
- Ground cover type (grass, moss, dirt, gravel, sand)
- Weathering/erosion patterns

**Prompt template for terrain analysis:**

```
Analyze this terrain reference image for procedural generation parameters:
1. What percentage is vegetation vs exposed rock vs bare ground?
2. Describe the dominant ground texture pattern (smooth, rocky, cracked, mossy)
3. What is the apparent moisture level? (dry, damp, wet, waterlogged)
4. Estimate roughness: smooth (0.1-0.3), medium (0.4-0.6), rough (0.7-0.9), very rough (0.9+)
5. Are there any special features? (glowing elements, water pools, crystal formations)
6. What terrain type does this suggest? (flat, hills, mountains, plains, chaotic)
Return as structured JSON with keys: vegetation_pct, rock_pct, ground_pct,
texture_pattern, moisture, roughness_estimate, special_features, terrain_type
```

**Confidence:** MEDIUM -- zai image analysis works well for compositional questions but may be inconsistent with precise numerical estimates. Use as guidance, not gospel.

---

## 2. Text-to-Generation Pipeline

### Converting Text Descriptions to Generation Parameters

The key insight from LLM-driven procedural generation research: use a structured intermediate representation between natural language and generation parameters. Do NOT try to parse free text directly into numbers.

**Architecture: Two-stage LLM pipeline**

Stage 1: Text --> Structured Biome Description (JSON)
Stage 2: Structured Description --> BIOME_PALETTES_V2 entry + VB_BIOME_PRESETS entry

**Stage 1 prompt template (for Claude or any LLM):**

```
You are a terrain artist for a dark fantasy medieval action RPG.
Convert this biome description into structured terrain parameters.

BIOME DESCRIPTION: "{user_description}"

Return JSON with these exact keys:
{
  "biome_name": "snake_case_name",
  "description": "one-line summary",
  "terrain_type": one of ["flat", "hills", "mountains", "plains", "chaotic"],
  "height_scale": float 2.0-50.0,
  "erosion_intensity": "none" | "light" | "moderate" | "heavy",
  "layers": {
    "ground": {
      "description": "what the ground looks like",
      "base_material": "terrain" | "stone" | "organic" | "wood",
      "roughness": float 0.1-1.0,
      "moisture": "dry" | "damp" | "wet"
    },
    "slope": { ... same structure ... },
    "cliff": { ... same structure ... },
    "special": {
      "description": "unique feature",
      "base_material": "...",
      "has_emission": bool,
      "emission_hue": "purple" | "green" | "blue" | "orange" | null,
      "has_transparency": bool
    }
  },
  "vegetation": {
    "density": "none" | "sparse" | "moderate" | "dense" | "overgrown",
    "types": ["list", "of", "plant", "types"],
    "scale_range": [min, max]
  },
  "scatter_props": ["list", "of", "environmental", "props"],
  "mood": "ominous" | "desolate" | "mystical" | "corrupted" | "serene"
}
```

**Stage 2: Map structured description to actual parameter values**

```python
# Mapping tables for Stage 2 conversion
ROUGHNESS_FROM_MOISTURE = {
    "dry": (0.80, 0.95),    # high roughness
    "damp": (0.50, 0.75),   # medium
    "wet": (0.10, 0.35),    # low roughness = shiny/wet
}

EROSION_ITERATIONS = {
    "none": 0,
    "light": 1000,
    "moderate": 3000,
    "heavy": 5000,
}

VEGETATION_DENSITY_MAP = {
    "none": 0.0,
    "sparse": 0.08,
    "moderate": 0.20,
    "dense": 0.35,
    "overgrown": 0.50,
}

NODE_RECIPE_FROM_MATERIAL = {
    "terrain": "terrain",
    "stone": "stone",
    "organic": "organic",
    "wood": "wood",
}

def structured_to_biome_palette(desc: dict) -> dict:
    """Convert Stage 1 structured description to BIOME_PALETTES_V2 entry."""
    palette = {}
    for layer_name in ("ground", "slope", "cliff", "special"):
        layer_desc = desc["layers"][layer_name]
        roughness_range = ROUGHNESS_FROM_MOISTURE.get(
            layer_desc.get("moisture", "damp"), (0.50, 0.75)
        )
        roughness = (roughness_range[0] + roughness_range[1]) / 2

        entry = {
            "base_color": (0.10, 0.08, 0.06, 1.0),  # placeholder -- filled by image analysis
            "roughness": roughness,
            "roughness_variation": 0.12,
            "metallic": 0.0,
            "normal_strength": 0.8,
            "detail_scale": 8.0,
            "wear_intensity": 0.25,
            "node_recipe": NODE_RECIPE_FROM_MATERIAL.get(
                layer_desc.get("base_material", "terrain"), "terrain"
            ),
            "description": layer_desc["description"],
        }

        # Special layer extras
        if layer_name == "special" and layer_desc.get("has_emission"):
            hue_colors = {
                "purple": (0.15, 0.02, 0.20, 1.0),
                "green": (0.05, 0.25, 0.05, 1.0),
                "blue": (0.05, 0.08, 0.25, 1.0),
                "orange": (0.30, 0.15, 0.02, 1.0),
            }
            entry["emission_color"] = hue_colors.get(
                layer_desc.get("emission_hue", "purple"),
                (0.15, 0.02, 0.20, 1.0)
            )
            entry["emission_strength"] = 0.4

        if layer_desc.get("has_transparency"):
            entry["alpha"] = 0.5

        palette[layer_name] = entry

    return palette
```

**Example conversion:**

Input: `"moss-covered granite cliff face with pine trees and morning mist"`

Stage 1 output:
```json
{
  "biome_name": "misty_granite_cliffs",
  "terrain_type": "mountains",
  "height_scale": 35.0,
  "erosion_intensity": "heavy",
  "layers": {
    "ground": {"description": "pine needle carpet over granite gravel", "base_material": "terrain", "roughness": 0.85, "moisture": "damp"},
    "slope": {"description": "moss-covered granite with lichen patches", "base_material": "stone", "roughness": 0.70, "moisture": "damp"},
    "cliff": {"description": "exposed granite face with cracks", "base_material": "stone", "roughness": 0.80, "moisture": "dry"},
    "special": {"description": "morning mist ground layer", "base_material": "terrain", "has_emission": false, "has_transparency": true}
  },
  "vegetation": {"density": "moderate", "types": ["pine_tree", "fern", "moss_patch"], "scale_range": [0.8, 1.4]},
  "scatter_props": ["boulder", "fallen_log", "pine_cone_cluster"],
  "mood": "mystical"
}
```

---

## 3. Tripo AI for Environmental Models

### Best Prompts for Dark Fantasy Terrain Props

Based on Tripo's prompt engineering guide and the existing `_settlement_grammar.py` patterns, use this template:

```
[object description], dark fantasy medieval style, weathered aged condition,
hand-crafted artisan quality, game-ready 3D model, clean topology,
PBR materials, low-poly optimized
(negative: no modern elements, no bright colors, no plastic appearance,
no thin sections, no complex overhangs)
```

**Terrain prop prompt library:**

| Prop Type | Prompt |
|-----------|--------|
| Forest rock | `"moss-covered granite boulder with cracks, dark fantasy medieval, weathered, organic shape, game-ready, PBR (negative: no sharp edges, no geometric)"` |
| Dead tree | `"gnarled dead tree trunk with twisted branches, dark fantasy, bark peeling, leafless, game-ready 3D model (negative: no leaves, no bright colors)"` |
| Pine tree | `"dark pine tree with sparse needles, medieval fantasy forest, slightly twisted trunk, game-ready low-poly (negative: no perfect symmetry)"` |
| Fallen log | `"moss-covered fallen log with mushrooms growing, dark fantasy forest floor, decaying wood, game-ready (negative: no modern elements)"` |
| Mushroom cluster | `"cluster of dark fantasy mushrooms, bioluminescent caps, forest floor, organic shapes, game-ready 3D model (negative: no cartoon style)"` |
| Stone ruins | `"crumbling stone block ruin fragment, medieval dark fantasy, moss and vine growth, game-ready (negative: no modern construction)"` |
| Crystal shard | `"dark crystal formation shard, purple-tinted translucent, emerging from rock base, fantasy game prop (negative: no bright colors)"` |

### Tripo API Settings for Terrain Props

```python
TERRAIN_PROP_TRIPO_SETTINGS = {
    "model_version": "v2.5-20250123",  # latest as of research date
    "texture": True,
    "pbr": True,
    "face_limit": 5000,       # game-ready poly budget
    "smart_low_poly": True,   # cleaner retopology
    "style": None,            # use prompt-driven style, not presets
    "texture_quality": "high",
}
```

### Style Consistency Strategy

1. **Prompt prefix system** -- All terrain prop prompts begin with `"dark fantasy medieval, weathered aged"`. This is already implemented in `_settlement_grammar.py` via `CORRUPTION_DESCS`.

2. **Post-generation material override** -- After Tripo import, apply VeilBreakers material correction:
   - Clamp all material values to dark fantasy ranges
   - Apply weathering overlay using existing `weathering.py` handlers
   - Use `blender_viewport action=contact_sheet` for visual verification

3. **Batch consistency** -- Generate all props for a single biome in one session with identical prompt prefixes. The Tripo model produces more stylistically consistent results when prompts share the same style descriptors.

### Quality Validation Pipeline for Tripo Meshes

```python
TERRAIN_PROP_QUALITY_THRESHOLDS = {
    "max_tris": 10000,        # terrain props should be lightweight
    "min_tris": 100,          # too few = broken/degenerate
    "max_dimensions": 10.0,   # meters -- props shouldn't be enormous
    "min_dimensions": 0.1,    # too small = failed generation
    "uv_coverage_min": 0.3,   # at least 30% UV space used
    "has_materials": True,     # must have at least one material
    "non_manifold_max": 10,   # allow some non-manifold edges
}

async def validate_tripo_prop(glb_path: str) -> dict:
    """Validate a Tripo-generated terrain prop meets quality thresholds.

    Run via blender_mesh action=game_check, then apply additional
    terrain-specific checks.
    """
    # Step 1: Import and run game_check
    # Step 2: Check dimensions match expected prop scale
    # Step 3: Verify material base_color is within dark fantasy range
    # Step 4: Take contact_sheet screenshot for zai visual validation
    # Step 5: Use analyze_image to verify "does this look like [prop_type]?"
    pass
```

### Batch Generation Strategy

Generate all props for a biome in parallel using asyncio:

```python
async def batch_generate_biome_props(
    biome_name: str,
    prop_list: list[str],
    corruption_band: str = "weathered",
) -> dict[str, str]:
    """Generate all props for a biome via Tripo, returning {prop_type: glb_path}."""
    tasks = []
    for prop_type in prop_list:
        prompt = build_terrain_prop_prompt(prop_type, corruption_band)
        tasks.append(generate_single_prop(prop_type, prompt))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return {
        prop_type: result
        for prop_type, result in zip(prop_list, results)
        if isinstance(result, str)
    }
```

---

## 4. Reference-Driven Material Creation

### Photo-to-Procedural Material Pipeline

The goal is NOT to create image-based textures (those require UV mapping and tiling). Instead, extract the visual characteristics from a reference photo and translate them into parameters for the existing procedural node recipes (`terrain`, `stone`, `organic`, `wood`).

**Step 1: Color extraction** (covered in Section 1 above)

**Step 2: Roughness estimation from image analysis**

Use the zai `analyze_image` tool with a focused prompt:

```
Analyze this terrain surface photo for material properties:
1. Surface roughness: very smooth (0.1), smooth (0.3), medium (0.5), rough (0.7), very rough (0.9)
2. Surface wetness: dry, slightly damp, wet, waterlogged
3. Pattern type: uniform, noisy, voronoi-like, layered, cracked
4. Pattern scale: fine (high frequency), medium, coarse (low frequency)
5. Normal map intensity suggestion: flat (0.2-0.4), moderate (0.5-0.8), pronounced (0.9-1.5), extreme (1.5+)
Return as JSON: {roughness, wetness, pattern_type, pattern_scale, normal_strength}
```

**Step 3: Map to procedural node parameters**

```python
PATTERN_TO_NOISE_PARAMS = {
    "uniform": {"noise_scale": 12.0, "noise_detail": 2.0, "voronoi_weight": 0.0},
    "noisy": {"noise_scale": 8.0, "noise_detail": 6.0, "voronoi_weight": 0.2},
    "voronoi-like": {"noise_scale": 6.0, "noise_detail": 4.0, "voronoi_weight": 0.7},
    "layered": {"noise_scale": 4.0, "noise_detail": 8.0, "voronoi_weight": 0.1},
    "cracked": {"noise_scale": 5.0, "noise_detail": 3.0, "voronoi_weight": 0.9},
}

SCALE_MAP = {
    "fine": 14.0,
    "medium": 8.0,
    "coarse": 4.0,
}

def image_analysis_to_material_params(
    analysis: dict,
    extracted_colors: list[tuple[float, float, float, float]],
) -> dict:
    """Convert zai image analysis + color extraction to material parameters."""
    pattern_params = PATTERN_TO_NOISE_PARAMS.get(
        analysis.get("pattern_type", "noisy"),
        PATTERN_TO_NOISE_PARAMS["noisy"],
    )
    return {
        "base_color": extracted_colors[0] if extracted_colors else (0.10, 0.08, 0.06, 1.0),
        "roughness": analysis.get("roughness", 0.8),
        "roughness_variation": 0.12,
        "metallic": 0.0,
        "normal_strength": analysis.get("normal_strength", 0.8),
        "detail_scale": SCALE_MAP.get(analysis.get("pattern_scale", "medium"), 8.0),
        "wear_intensity": 0.25,
        "node_recipe": "terrain",
    }
```

### Matching Weathering Patterns

The existing `weathering.py` handler already provides weathering overlays. The research pipeline should:

1. Analyze reference image for weathering characteristics (moss coverage, erosion marks, staining)
2. Map to weathering parameters: `wear_intensity` (0.0-1.0), `moss_coverage` (0.0-1.0)
3. Apply via the existing weathering system after base material creation

**Confidence:** HIGH for color extraction, MEDIUM for roughness/pattern estimation via LLM vision.

---

## 5. Proposed Pipeline Architecture

### Complete Flow

```
User Input: biome_name="thornwood_forest"
             OR
             biome_description="moss-covered granite cliff with pine trees"
             research_mode=True
                    |
                    v
    +-------------------------------+
    | 1. CHECK BIOME_PALETTES_V2    |
    |    Known biome? Use it.       |
    |    Unknown OR research_mode?  |
    |    Continue to step 2.        |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 2. WEB SEARCH FOR REFERENCES  |
    |    Pexels API: terrain photos  |
    |    Query: "{biome} terrain     |
    |      landscape dark fantasy"   |
    |    Fetch top 5 images          |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 3. ANALYZE REFERENCES         |
    |    a) KMeans color extraction  |
    |       -> dominant colors       |
    |    b) zai analyze_image        |
    |       -> terrain composition   |
    |       -> roughness/pattern     |
    |    c) Enforce dark fantasy     |
    |       palette constraints      |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 4. GENERATE BIOME DEFINITION  |
    |    a) LLM Stage 1: text ->    |
    |       structured description   |
    |    b) Merge with image data:   |
    |       - Colors from extraction |
    |       - Roughness from zai     |
    |    c) Output:                  |
    |       - BIOME_PALETTES_V2 entry|
    |       - VB_BIOME_PRESETS entry |
    |       - Scatter rules          |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 5. GENERATE MISSING PROPS     |
    |    For each scatter_rule prop: |
    |    a) Check prop cache         |
    |    b) If missing: Tripo gen    |
    |       with dark fantasy prompt |
    |    c) Validate quality         |
    |    d) Post-process (delight)   |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 6. GENERATE TERRAIN           |
    |    Standard pipeline:          |
    |    terrain -> materials ->     |
    |    scatter -> water -> roads   |
    +-------------------------------+
                    |
                    v
    +-------------------------------+
    | 7. VISUAL QA                  |
    |    a) contact_sheet render     |
    |    b) zai comparison with      |
    |       reference images         |
    |    c) Score: does generated    |
    |       terrain match reference? |
    |    d) If score < threshold:    |
    |       adjust params, retry     |
    +-------------------------------+
```

### Implementation as a New Handler

Add to the Blender server as a new action on the `asset_pipeline` tool:

```python
# New action: asset_pipeline action=research_biome
# Parameters:
#   biome_name: str (existing or new)
#   biome_description: str (natural language description)
#   research_mode: bool (force web research even for known biomes)
#   reference_count: int (number of reference images to fetch, default 5)
#   auto_generate: bool (if True, immediately generate terrain after research)
```

### Module Structure

```
blender_addon/handlers/
    terrain_research.py          # NEW: web research + image analysis
        fetch_terrain_references()     # Pexels API integration
        extract_palette_from_image()   # KMeans color extraction
        analyze_terrain_image()        # zai tool integration
        enforce_dark_fantasy()         # palette constraint enforcement
        text_to_biome_params()         # LLM structured conversion
        generate_biome_definition()    # Full pipeline orchestrator
        compare_with_reference()       # Visual QA comparison
```

### Integration Points with Existing System

| Existing Module | Integration |
|----------------|-------------|
| `terrain_materials.py` | New biome entries injected into `BIOME_PALETTES_V2` at runtime |
| `environment.py` | New biome presets injected into `VB_BIOME_PRESETS` at runtime |
| `_settlement_grammar.py` | Tripo prompt templates extended for terrain props |
| `worldbuilding.py` | `get_or_generate_prop()` reused for prop generation |
| `weathering.py` | Post-generation weathering applied based on research analysis |
| `pipeline_runner.py` | `generate_3d` action called for Tripo prop generation |

### Runtime Registration Pattern

Do NOT modify the hardcoded dictionaries. Instead, use runtime registration:

```python
# In terrain_research.py
def register_researched_biome(
    biome_name: str,
    palette: dict,
    preset: dict,
) -> None:
    """Register a dynamically-researched biome into the runtime biome system."""
    from .terrain_materials import BIOME_PALETTES_V2
    from .environment import VB_BIOME_PRESETS

    BIOME_PALETTES_V2[biome_name] = palette
    VB_BIOME_PRESETS[biome_name] = preset
    logger.info("Registered researched biome: %s", biome_name)
```

### Caching Strategy

```python
RESEARCH_CACHE_DIR = Path.home() / ".veilbreakers" / "research_cache"

# Cache structure:
# ~/.veilbreakers/research_cache/
#     biomes/
#         thornwood_forest/
#             references/          # downloaded reference images
#             palette.json         # extracted color palette
#             analysis.json        # zai terrain analysis
#             biome_definition.json  # generated BIOME_PALETTES_V2 entry
#             props/               # generated Tripo GLB files
#     props/
#         forest_rock_weathered.glb
#         dead_tree_corrupted.glb
```

---

## 6. Quality Comparison and Feedback Loop

### Visual QA Pipeline

**Step 1: Render the generated terrain**

Use `blender_viewport action=contact_sheet` to capture 4-6 angles of the generated terrain.

**Step 2: Compare against reference images**

Use the `ui_diff_check` zai tool with this prompt:

```
Compare these two images:
IMAGE 1 (REFERENCE): A real terrain photo of [biome_description]
IMAGE 2 (GENERATED): A procedurally generated terrain meant to match the reference

Score the following (1-10):
1. Color palette match: Do the dominant colors match?
2. Terrain roughness match: Does surface detail level match?
3. Vegetation density match: Is plant coverage similar?
4. Mood/atmosphere match: Does the generated scene evoke the same feeling?
5. Overall realism: How photorealistic does the generated terrain look?

Return JSON: {color_score, roughness_score, vegetation_score, mood_score, realism_score, overall_score, suggestions: [list of improvements]}
```

**Step 3: Automated parameter adjustment**

```python
ADJUSTMENT_RULES = {
    "color_score < 5": "Re-extract palette from more reference images, increase KMeans clusters",
    "roughness_score < 5": "Adjust roughness +-0.15 toward reference analysis value",
    "vegetation_score < 5": "Scale vegetation density by 1.5x or 0.5x",
    "mood_score < 5": "Adjust lighting, add fog, modify special layer emission",
    "overall_score < 4": "Full re-research with different search queries",
}

MAX_REFINEMENT_ITERATIONS = 3  # prevent infinite loops
```

### Automated Scoring Without zai (Fallback)

If zai tools are unavailable, use pixel-based comparison:

```python
def compare_color_histograms(
    reference_path: str,
    generated_path: str,
) -> float:
    """Compare color distributions using histogram intersection.

    Returns similarity score 0.0 (no match) to 1.0 (identical).
    """
    from PIL import Image
    import numpy as np

    ref = np.array(Image.open(reference_path).resize((256, 256)).convert("RGB"))
    gen = np.array(Image.open(generated_path).resize((256, 256)).convert("RGB"))

    # Compute color histograms in HSV space
    # Compare using histogram intersection
    ref_hist = np.histogram(ref.reshape(-1, 3), bins=32, range=(0, 256))[0]
    gen_hist = np.histogram(gen.reshape(-1, 3), bins=32, range=(0, 256))[0]

    # Normalize
    ref_hist = ref_hist / ref_hist.sum()
    gen_hist = gen_hist / gen_hist.sum()

    # Intersection
    return float(np.minimum(ref_hist, gen_hist).sum())
```

---

## 7. Dependencies and Environment Requirements

### New Dependencies Required

| Package | Version | Purpose | Already in Project? |
|---------|---------|---------|---------------------|
| httpx | >=0.27 | Pexels API calls | YES (used for Tripo) |
| Pillow | >=10.0 | Image loading/resizing | YES (used for textures) |
| scikit-learn | >=1.4 | KMeans color extraction | CHECK -- may need to add |
| numpy | >=1.26 | Array operations | YES |

### Environment Variables

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `PEXELS_API_KEY` | YES for web research | Pexels image API access |
| `TRIPO_API_KEY` | Already exists | 3D prop generation |

### MCP Tool Dependencies

| Tool | Used For | Required? |
|------|----------|-----------|
| `analyze_image` (zai) | Terrain image analysis | Optional (LLM fallback) |
| `ui_diff_check` (zai) | QA comparison | Optional (histogram fallback) |
| `web_search_prime` | Alternative image search | Optional (Pexels primary) |
| `asset_pipeline generate_3d` | Tripo prop generation | YES |
| `blender_viewport contact_sheet` | Visual QA renders | YES |

---

## 8. Critical Pitfalls

### Pitfall 1: Image Search Returns Irrelevant Results
**Problem:** Searching "dark forest terrain" returns video game screenshots, not real terrain photos.
**Prevention:** Add `"-game -screenshot -render -3d -cgi"` to search queries. Use Pexels "nature" category filter. Validate with zai that the image is a real photograph before using for color extraction.

### Pitfall 2: Color Extraction Produces Unrealistic Palettes
**Problem:** KMeans can be dominated by sky/background colors in landscape photos.
**Prevention:** Crop to bottom 60% of image (terrain, not sky). Weight by pixel area. Validate extracted colors against dark fantasy constraints before use.

### Pitfall 3: LLM Hallucination in Parameter Conversion
**Problem:** The LLM in Stage 1 may generate implausible parameter combinations (e.g., "smooth wet granite" with roughness 0.95).
**Prevention:** Apply hard constraints after LLM output. Use the mapping tables, not raw LLM numbers. Cross-validate: if LLM says "wet" but suggests roughness 0.9, override to wet roughness range.

### Pitfall 4: Tripo API Rate Limits and Costs
**Problem:** Generating 10-15 props per biome is expensive and slow.
**Prevention:** Cache aggressively. Check prop cache before generation. Reuse generic props across biomes (rocks, logs). Only generate biome-specific unique props (mushroom clusters, crystal shards).

### Pitfall 5: Research Pipeline is Too Slow for Interactive Use
**Problem:** Web search + image download + analysis + generation = minutes, not seconds.
**Prevention:** Make research an offline/background process. Cache results. Provide a `research_biome` CLI command that runs ahead of time. Never block the interactive terrain generation path on web research.

### Pitfall 6: scikit-learn May Not Be Available in Blender Python
**Problem:** Blender ships its own Python and may not have sklearn.
**Prevention:** Implement KMeans manually (it is a 30-line algorithm) or use a pure-Python implementation. Do NOT depend on sklearn inside the Blender addon -- only use it in the MCP server side. The Blender addon receives pre-computed palette data, not raw images.

---

## 9. Implementation Phases

### Phase 1: Color Extraction Pipeline (LOW risk, HIGH value)
- Implement `fetch_terrain_references()` with Pexels API
- Implement `extract_terrain_palette()` with KMeans
- Implement `enforce_dark_fantasy_palette()`
- Write tests with sample terrain images
- Integrate: existing biomes get reference-validated palettes

### Phase 2: LLM Text-to-Parameters (MEDIUM risk, HIGH value)
- Implement Stage 1 structured conversion prompt
- Implement Stage 2 parameter mapping tables
- Implement `register_researched_biome()` runtime injection
- Write tests with 5-10 biome descriptions
- Integrate: `asset_pipeline action=research_biome`

### Phase 3: Tripo Terrain Props (MEDIUM risk, MEDIUM value)
- Build terrain prop prompt library
- Implement batch generation pipeline
- Implement quality validation
- Write tests for prop validation thresholds
- Integrate: auto-generate missing scatter props

### Phase 4: Visual QA Loop (HIGH risk, HIGH value)
- Implement contact_sheet comparison
- Implement zai-based scoring
- Implement histogram fallback
- Implement automated parameter adjustment
- Write tests for refinement loop termination

---

## Sources

- [Pexels API Documentation](https://www.pexels.com/api/documentation/)
- [Unsplash API Documentation](https://unsplash.com/documentation)
- [Pylette -- Python Color Palette Extraction](https://github.com/qTipTip/Pylette)
- [KMeans Color Clustering (PyImageSearch)](https://pyimagesearch.com/2014/05/26/opencv-python-k-means-color-clustering/)
- [Tripo AI Prompt Engineering Guide](https://www.tripo3d.ai/blog/text-to-3d-prompt-engineering)
- [Tripo API Generation Docs](https://platform.tripo3d.ai/docs/generation)
- [Tripo Low Poly Model Guide](https://www.tripo3d.ai/content/en/use-case/the-best-low-poly-model-maker)
- [VLMaterial: Procedural Material Generation with VLMs (arXiv)](https://arxiv.org/html/2501.18623v2)
- [PCG with LLMs Survey (arXiv)](https://arxiv.org/html/2410.15644v1)
- [LLM-Driven Procedural Terrain Generator (GitHub)](https://github.com/pkunjam/Confluent-AI-LLM-Driven-Procedural-Terrain-Generator)
- [Narrative-to-Scene Generation Pipeline (arXiv)](https://www.arxiv.org/pdf/2509.04481)
