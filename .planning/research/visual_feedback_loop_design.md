# Visual Feedback Loop System Design
## AI-Driven Iterative Quality Improvement for VeilBreakers Procedural Generation

**Date:** 2026-04-03
**Status:** Research Complete / Ready for Implementation Planning

---

## 1. Executive Summary

This document designs a **Generate-Verify-Fix (GVF) loop** where the AI agent creates 3D content via MCP tools, captures multi-angle screenshots, analyzes them for quality issues using a tiered evaluation pipeline (cheap pixel checks first, expensive multimodal LLM review second), identifies specific problems, applies targeted fixes, and re-captures to verify -- repeating until a quality threshold is met or a budget is exhausted.

The system builds on VeilBreakers' existing infrastructure:
- `blender_viewport` action=`contact_sheet` (multi-angle renders)
- `visual_validation.py` (pixel-based scoring: brightness, contrast, edges, entropy)
- `screenshot_diff.py` (regression detection via pixel diff)
- `gemini_client.py` (Gemini 2.0 Flash visual review with structured JSON output)
- `asset_pipeline` action=`aaa_verify` (10-angle quality gate with floating geometry and default material detection)

The innovation is closing the loop: **today these tools are one-shot checks; the new system makes them iterative with targeted remediation.**

---

## 2. Research Findings

### 2.1 State of AI-in-the-Loop 3D Generation (2024-2026)

**GPTEval3D (CVPR 2024)** demonstrated that GPT-4V is a human-aligned evaluator for text-to-3D generation. The method renders 3D assets from multiple viewpoints, feeds them to GPT-4V with evaluation criteria, uses pairwise comparison to generate Elo ratings, and employs ensemble techniques (multiple perturbed inputs) to stabilize probabilistic outputs. This validates our core premise: multimodal LLMs can reliably judge 3D render quality.

**Round-Trip Screenshot Testing** (Tal Rotbart, Feb 2026) established the pattern for Claude Code: write code, render through a real system, capture what it actually produced, and inspect the result. This closes the fundamental feedback loop where AI operates blind. The implementation uses a screenshot harness that captures PNGs around every action, plus an orchestrator that drives the full flow.

**The Agentic Coding Handbook** (Tweag) documents the Visual Feedback Loop workflow: capture screenshots after each iteration, feed them back to the AI with structured prompts, and iterate until visual diff is negligible. They note this makes "invisible problems visible -- especially spacing, color, and layout inconsistencies."

**AvatarForge** combines LLM-driven commonsense reasoning with real-time procedural 3D generation, validating that LLMs can reason about 3D content from rendered images when given the right reference language.

**Marble** (2025) generates persistent, downloadable 3D environments from text/images with Unity/Unreal export, showing the industry direction for AI-generated 3D content.

### 2.2 Key Insight: Multi-Angle Rendering is Essential

Research consistently shows that multimodal LLMs cannot directly consume 3D information -- they must work from rendered 2D images. GPTEval3D renders from multiple viewpoints; Dave Snider's Claude 3D tips confirm "when presented a set of images of 3D space from different angles, along with the right reference language, Claude can usually figure something out."

Our existing `contact_sheet` (6 angles) and `aaa_verify` (10 angles) already provide this. The GVF loop extends these with **targeted angle selection** based on which problems are detected.

### 2.3 Image Token Costs and Resolution

- **1000x1000px image ~= 1,334 tokens** (GPT-4o baseline)
- GPT-4o low-detail mode: 85 tokens regardless of size
- GPT-4o high-detail mode: 85 + 170 tokens per 512x512 tile
- Gemini charges ~560 tokens per input image (Gemini 3 Pro)
- Claude processes images internally via Vision Transformer with intelligent downscaling

**Practical resolution targets:**
- Fast automated checks: **256x256** (negligible token cost, good for pixel analysis)
- Standard AI review: **512x512** (good detail-to-cost ratio, ~4 tiles in GPT-4o)
- Detailed AI review: **1024x1024** (maximum useful detail, diminishing returns above this)
- Contact sheets: **768px per cell, 3x2 grid = 2304x1536** (one image, 6 angles)

### 2.4 Cost Analysis (Gemini 2.0 Flash, current pricing)

- Input: $0.50 per million tokens (Gemini 3 Flash)
- Output: $3.00 per million tokens
- Image: ~560 tokens per image
- Estimated cost per GVF iteration (10 screenshots + structured prompt):
  - Image tokens: 10 x 560 = 5,600 tokens
  - Prompt + context: ~2,000 tokens
  - Output (structured JSON): ~500 tokens
  - **Total: ~8,100 tokens = $0.0056 per iteration**
  - **10-iteration loop: ~$0.056**
  - **100 scenes per session: ~$5.60**

This is negligible. We can afford aggressive iteration.

---

## 3. Architecture

### 3.1 Three-Tier Evaluation Pipeline

```
TIER 1: Pixel Analysis (FREE, <100ms)
  - visual_validation.py: brightness, contrast, edges, entropy, color spread
  - screenshot_diff.py: regression detection against baselines
  - New: silhouette analysis, ground plane contact, symmetry checks
  - New: color palette compliance (dark fantasy earth tones)
  - Gate: score >= 55 to proceed to Tier 2

TIER 2: Structural Analysis (FREE, <500ms)
  - Blender-side mesh checks via blender_mesh action=game_check
  - Floating geometry detection (existing: bottom 20% brightness)
  - Default material detection (existing: low color variance)
  - New: Object overlap detection via bounding box queries
  - New: Scale/proportion validation against reference measurements
  - New: Ground contact verification via raycasting
  - Gate: no critical structural issues to proceed to Tier 3

TIER 3: Semantic Analysis (PAID, ~2s)
  - Gemini 2.0 Flash with structured prompt + multi-angle screenshots
  - Dark fantasy quality rubric (10 dimensions, 1-10 each)
  - Specific issue identification with spatial references
  - Actionable fix suggestions mapped to MCP tool calls
  - Gate: overall score >= 7.0 / no dimension below 4.0
```

### 3.2 System Components

```
visual_feedback_loop.py (NEW - orchestrator)
  |
  +-- quality_rubric.py (NEW - scoring dimensions and prompts)
  |
  +-- visual_validation.py (EXISTING - pixel analysis, extended)
  |
  +-- screenshot_diff.py (EXISTING - regression detection)
  |
  +-- gemini_client.py (EXISTING - Gemini API, extended with rubric prompts)
  |
  +-- issue_mapper.py (NEW - maps detected issues to MCP fix actions)
  |
  +-- iteration_budget.py (NEW - cost/time budget tracking)
  |
  +-- blender_client.py (EXISTING - viewport capture)
```

### 3.3 Data Flow

```
                    +------------------+
                    | Generate Content |  (blender_worldbuilding, blender_quality, asset_pipeline)
                    +--------+---------+
                             |
                             v
                    +------------------+
                    | Capture Screens  |  (blender_viewport contact_sheet, 10-angle aaa_verify)
                    +--------+---------+
                             |
                    +--------v---------+
                    | Tier 1: Pixels   |  (visual_validation.analyze_render_image)
                    +--------+---------+
                             |
                     pass?  / \  fail?
                           /   \
                          v     v
                    +------+  +------------------+
                    |Tier 2|  | Quick Fix        |  (auto-remediate: lighting, contrast)
                    +--+---+  +--------+---------+
                       |               |
                       |      +--------v---------+
                       |      | Re-Capture       |
                       |      +--------+---------+
                       |               |
                       +<--------------+
                       |
                  pass?/ \ fail?
                      /   \
                     v     v
               +------+  +------------------+
               |Tier 3|  | Structural Fix   |  (move objects, fix materials)
               +--+---+  +--------+---------+
                  |                |
                  |       +--------v---------+
                  |       | Re-Capture       |
                  |       +--+--------------+
                  |          |
                  +<---------+
                  |
             pass?/ \ fail?
                 /   \
                v     v
          +--------+ +------------------+
          | ACCEPT | | Semantic Fix     |  (rearrange, restyle, relight)
          +--------+ +--------+---------+
                              |
                     +--------v---------+
                     | Re-Capture       |
                     +--------+---------+
                              |
                     +--------v---------+
                     | Budget Check     |  (max iterations? time limit? cost limit?)
                     +--------+---------+
                              |
                      exhaust?/ \ budget ok?
                             /   \
                            v     v
                     +--------+ +------------------+
                     | ACCEPT | | Loop to Tier 1   |
                     | (warn) | +------------------+
                     +--------+
```

---

## 4. Quality Rubric: Dark Fantasy Scoring Dimensions

### 4.1 The 10 Dimensions

Each dimension is scored 1-10 by the Gemini reviewer. The rubric includes reference descriptions for scores 1, 5, and 10 to anchor the model's judgment.

| # | Dimension | Weight | Min Pass | Description |
|---|-----------|--------|----------|-------------|
| 1 | **Composition** | 0.10 | 4 | Scene arrangement, focal points, visual flow, rule of thirds |
| 2 | **Atmosphere** | 0.15 | 5 | Dark, moody, threatening feel; oppressive vs inviting balance |
| 3 | **Material Quality** | 0.12 | 5 | Weathered, aged, realistic surfaces; no plastic or default gray |
| 4 | **Lighting** | 0.12 | 5 | Warm islands in cold darkness, dramatic shadows, volumetric feel |
| 5 | **Prop Placement** | 0.10 | 4 | Logical, grounded, storytelling; no floating, no wall-clipping |
| 6 | **Architectural Coherence** | 0.10 | 5 | Structural plausibility, load-bearing logic, style consistency |
| 7 | **Scale/Proportion** | 0.08 | 5 | Human-scale doors (~2m), appropriate room sizes, consistent scale |
| 8 | **Detail Density** | 0.08 | 4 | Enough clutter/detail without noise; lived-in feel |
| 9 | **Color Palette** | 0.08 | 5 | Desaturated earth tones, no bright/saturated outliers |
| 10 | **Storytelling** | 0.07 | 3 | Environment suggests history, events, inhabitants |

**Overall score** = weighted sum. **Pass threshold** = 7.0 overall AND no dimension below its min pass.

### 4.2 Gemini Prompt Template

```
SYSTEM: You are a senior environment artist reviewing procedurally generated 3D scenes
for a dark fantasy action RPG called VeilBreakers. The game has a late medieval Gothic
aesthetic: weathered stone and timber, dark earth palette, moody lighting.

You are shown {angle_count} camera angles of the same scene. Evaluate the scene against
the quality rubric below. For each dimension, provide:
- A score from 1 to 10
- A brief justification (1 sentence)
- If score < minimum pass, provide a specific fix action

SCORING ANCHORS:
- 1 = Unacceptable (default gray materials, random object placement, no atmosphere)
- 5 = Acceptable (basic materials applied, logical placement, some mood)
- 10 = AAA Quality (rich weathered textures, masterful composition, immersive atmosphere)

QUALITY RUBRIC:
1. Composition (min 4): Scene arrangement, focal points, visual flow
2. Atmosphere (min 5): Dark, moody, threatening. Late medieval Gothic feel.
3. Material Quality (min 5): Weathered stone, aged wood, rusted metal. No plastic or default gray.
4. Lighting (min 5): Warm torchlight islands in cold blue darkness. Dramatic shadows.
5. Prop Placement (min 4): Objects grounded on surfaces, logical positions, no clipping.
6. Architectural Coherence (min 5): Walls connect to floors, arches bear load, style consistent.
7. Scale/Proportion (min 5): Doors ~2m tall, chairs ~0.5m, rooms 3-8m across.
8. Detail Density (min 4): Enough props/clutter for lived-in feel, not overwhelming.
9. Color Palette (min 5): Desaturated earth tones (browns, grays, muted reds/greens). No bright colors.
10. Storytelling (min 3): Scene suggests who lived here, what happened, passage of time.

RESPOND IN THIS EXACT JSON FORMAT:
{
  "overall_score": <float 1.0-10.0>,
  "passed": <bool>,
  "dimensions": {
    "composition": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "atmosphere": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "material_quality": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "lighting": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "prop_placement": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "architectural_coherence": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "scale_proportion": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "detail_density": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "color_palette": {"score": <int>, "justification": "<str>", "fix": "<str or null>"},
    "storytelling": {"score": <int>, "justification": "<str>", "fix": "<str or null>"}
  },
  "critical_issues": [
    {"issue": "<str>", "location": "<str>", "severity": "critical|major|minor",
     "suggested_fix": "<str mapped to MCP action>"}
  ],
  "summary": "<1-2 sentence overall assessment>"
}
```

### 4.3 Few-Shot Calibration

To anchor the model's scoring, the prompt includes **reference pairs** (stored as baseline images):

```
FEW-SHOT EXAMPLES (included as images when available):
- "This is a SCORE 3 tavern interior" -> [image of bare room, default materials, random props]
- "This is a SCORE 7 tavern interior" -> [image of furnished room, basic materials, logical layout]
- "This is a SCORE 9 tavern interior" -> [image of richly detailed room, weathered textures, dramatic lighting]

Use these as calibration anchors. A score of 7 means "about as good as the middle example."
```

---

## 5. Issue-to-Fix Mapping

### 5.1 Automated Fix Actions

The `issue_mapper.py` component translates detected issues into MCP tool calls:

```python
ISSUE_FIX_MAP = {
    # Tier 1 pixel-level fixes
    "too_dark": {
        "tool": "blender_execute",
        "action": "Increase sun/point light energy by 50%, add fill light",
        "code_template": "bpy.data.lights['Sun'].energy *= 1.5"
    },
    "too_bright": {
        "tool": "blender_execute",
        "action": "Reduce light energy by 30%",
        "code_template": "for l in bpy.data.lights: l.energy *= 0.7"
    },
    "low_contrast": {
        "tool": "blender_execute",
        "action": "Increase key-to-fill ratio, add rim light",
    },
    "low_color_variation": {
        "tool": "blender_material",
        "action": "apply",
        "params": {"preset": "dark_fantasy_stone_weathered"}
    },
    "monochrome": {
        "tool": "blender_material",
        "action": "apply",
        "params": {"preset": "dark_fantasy_varied"}
    },

    # Tier 2 structural fixes
    "floating_geometry": {
        "tool": "blender_execute",
        "action": "Snap objects to ground plane via raycast",
        "code_template": "# raycast from object origin downward, snap to hit"
    },
    "default_material": {
        "tool": "blender_material",
        "action": "apply",
        "params": {"preset": "auto_from_object_name"}
    },
    "object_overlap": {
        "tool": "blender_execute",
        "action": "Separate overlapping objects by minimum bounding box gap",
    },
    "scale_violation": {
        "tool": "blender_object",
        "action": "transform",
        "params": {"operation": "scale_to_reference"}
    },

    # Tier 3 semantic fixes (require Gemini suggestions)
    "poor_composition": {
        "strategy": "redistribute_focal_points",
        "tool": "blender_execute",
        "description": "Move hero props to rule-of-thirds positions"
    },
    "weak_atmosphere": {
        "strategy": "enhance_mood_lighting",
        "tools": ["blender_execute", "blender_material"],
        "description": "Add fog, reduce ambient, warm point lights, add dust particles"
    },
    "plastic_materials": {
        "strategy": "weathering_pass",
        "tool": "blender_material",
        "description": "Apply weathering overlay: scratches, dirt, moss, rust"
    },
    "random_prop_placement": {
        "strategy": "semantic_rearrange",
        "tool": "blender_execute",
        "description": "Group props by function (dining area, storage, workspace)"
    },
    "no_storytelling": {
        "strategy": "add_narrative_props",
        "tool": "blender_worldbuilding",
        "description": "Add scattered papers, overturned furniture, bloodstains, cobwebs"
    },
}
```

### 5.2 Fix Prioritization

Fixes are applied in dependency order:
1. **Structural** first (floating objects, scale) -- these affect all other dimensions
2. **Materials** second (default gray, plastic) -- these affect atmosphere, color, storytelling
3. **Lighting** third (too dark/bright, contrast) -- this affects atmosphere, mood, composition
4. **Composition** fourth (focal points, arrangement) -- this affects storytelling, detail density
5. **Detail/Narrative** last (clutter, storytelling props) -- finishing touches

---

## 6. Iteration Budget and Convergence

### 6.1 Budget Parameters

```python
@dataclass
class IterationBudget:
    max_iterations: int = 5          # Hard cap on GVF loops
    max_time_seconds: float = 120.0  # Wall-clock time limit
    max_gemini_calls: int = 3        # Tier 3 calls are the expensive ones
    min_score_improvement: float = 0.5  # Stop if score improves < 0.5 per iteration
    target_score: float = 7.0        # Stop when overall >= 7.0
    emergency_accept_score: float = 5.0  # Accept at budget exhaustion if >= 5.0
```

### 6.2 Convergence Strategy

```
Iteration 1: Generate -> Tier 1 check -> auto-fix pixel issues
Iteration 2: Re-capture -> Tier 1+2 check -> auto-fix structural issues
Iteration 3: Re-capture -> Tier 1+2+3 check -> Gemini review -> semantic fixes
Iteration 4: Re-capture -> Tier 3 check -> verify Gemini fixes
Iteration 5: Final capture -> Tier 3 check -> accept or flag for human review
```

**Expected convergence:** Based on the Agentic Coding Handbook findings and our cost analysis:
- Most scenes should pass after **2-3 iterations** (pixel + structural fixes are deterministic)
- Complex scenes needing semantic rearrangement: **4-5 iterations**
- Pathological cases (fundamentally bad generation): **fail fast at iteration 2** and regenerate

### 6.3 When to Regenerate vs Fix

```python
def should_regenerate(tier1_result, tier2_result) -> bool:
    """Regeneration is cheaper than fixing if the base generation is terrible."""
    score = tier1_result["score"]
    issues = tier2_result.get("issues", [])

    # Score below 30 = hopeless, regenerate with different seed
    if score < 30:
        return True

    # More than 5 structural issues = too broken to fix
    if len([i for i in issues if "critical" in str(i)]) > 5:
        return True

    # Default material on >80% of objects = nothing was generated properly
    if "default_material_detected" in issues and score < 40:
        return True

    return False
```

---

## 7. New Pixel Analysis Extensions (Tier 1)

### 7.1 Dark Fantasy Palette Compliance

```python
def check_palette_compliance(image_path: str) -> dict:
    """Check if image colors match dark fantasy palette.

    Target palette: desaturated earth tones
    - Browns: HSV hue 15-45, saturation 20-60%, value 15-50%
    - Grays: any hue, saturation <15%, value 20-60%
    - Muted reds: hue 0-15, saturation 30-50%, value 20-45%
    - Muted greens: hue 80-140, saturation 15-40%, value 15-40%
    - Cold blues: hue 200-240, saturation 10-30%, value 15-35%

    Violations: bright saturated colors (S>70%, V>70%), neon, pastels
    """
```

### 7.2 Ground Contact Verification

```python
def check_ground_contact(image_path: str, ground_y_fraction: float = 0.7) -> dict:
    """Verify objects appear grounded (not floating).

    Analyzes the lower portion of the image for:
    - Shadow presence below objects (dark pixels near object bases)
    - Continuous contact lines (no sky-colored gaps between object and ground)
    - Object silhouettes that reach the expected ground plane
    """
```

### 7.3 Silhouette Complexity

```python
def check_silhouette_complexity(image_path: str) -> dict:
    """Evaluate visual complexity of object silhouettes.

    Low complexity = basic cubes/cylinders (score 1-3)
    Medium complexity = recognizable shapes with some detail (score 4-6)
    High complexity = organic, detailed silhouettes (score 7-10)

    Uses edge detection + contour analysis on alpha channel.
    """
```

---

## 8. Enhanced Gemini Client (Tier 3)

### 8.1 Extended GeminiReviewClient

```python
class GeminiQualityReviewer(GeminiReviewClient):
    """Extended Gemini client for GVF loop quality review."""

    RUBRIC_PROMPT = """..."""  # From section 4.2

    async def review_scene(
        self,
        screenshot_paths: list[str],
        scene_type: str = "interior",  # interior|exterior|dungeon|settlement
        few_shot_paths: dict[int, str] | None = None,  # {score: image_path}
        previous_review: dict | None = None,  # for delta tracking
    ) -> dict:
        """Multi-angle scene review with dark fantasy rubric.

        Args:
            screenshot_paths: 6-10 angle screenshots of the scene
            scene_type: Type hint for context-appropriate scoring
            few_shot_paths: Optional calibration images {score: path}
            previous_review: Previous iteration's review for delta tracking

        Returns:
            Structured rubric scores + issues + fix suggestions
        """

    async def review_batch(
        self,
        scenes: list[dict],  # [{name, paths, type}]
    ) -> list[dict]:
        """Batch multiple scenes into fewer API calls.

        Packs up to 4 scenes (as contact sheets) into a single Gemini call.
        Significantly reduces per-scene cost for settlement/town generation.
        """

    async def compare_iterations(
        self,
        before_paths: list[str],
        after_paths: list[str],
        applied_fixes: list[str],
    ) -> dict:
        """Compare before/after screenshots to verify fixes worked.

        Returns:
            {
                "improved": bool,
                "score_delta": float,
                "fixes_verified": list[str],
                "fixes_failed": list[str],
                "new_issues": list[str],
            }
        """
```

### 8.2 Batching Strategy

```
Single building:  1 contact sheet (6 angles) = 1 Gemini call
Room interior:    1 contact sheet (6 angles) = 1 Gemini call
Settlement:       4 contact sheets (4 buildings x 6 angles) = 1 Gemini call
Full map:         10 contact sheets batched as 3 Gemini calls
                  (3-4 sheets per call, ~20 images total)
```

**Cost for full map review:** ~3 Gemini calls x 8,100 tokens = ~$0.017

---

## 9. MCP Tool Integration

### 9.1 New Action: `asset_pipeline` action=`visual_feedback_loop`

```python
# Added to asset_pipeline tool
elif action == "visual_feedback_loop":
    """Run the full Generate-Verify-Fix loop on an object or scene.

    Params:
        object_name: Target object/collection to evaluate
        scene_type: interior|exterior|dungeon|settlement
        max_iterations: Override default iteration budget (default 5)
        target_score: Override target quality score (default 7.0)
        auto_fix: Whether to apply fixes automatically (default True)
        tier3_enabled: Whether to use Gemini review (default True)

    Returns:
        {
            "iterations": int,
            "initial_score": float,
            "final_score": float,
            "score_history": [float, ...],
            "fixes_applied": [str, ...],
            "final_review": {...rubric scores...},
            "screenshots": [str, ...],  # final angle screenshots
            "passed": bool,
            "budget_exhausted": bool,
        }
    """
```

### 9.2 New Action: `blender_viewport` action=`targeted_capture`

```python
# Added to blender_viewport tool
elif action == "targeted_capture":
    """Capture screenshots from specific angles targeting known issues.

    Params:
        object_name: Target object
        focus_areas: list of {"position": [x,y,z], "look_at": [x,y,z], "label": str}

    Use case: After Gemini identifies "chair facing wall at position (3,0,2)",
    capture a close-up of that specific area to verify the fix.
    """
```

### 9.3 Integration with Existing Workflows

The GVF loop hooks into existing generation flows:

```python
# In compose_map:
for location in map_spec["locations"]:
    result = await generate_location(location)
    # NEW: visual feedback loop per location
    if review_lighting:
        vfl_result = await visual_feedback_loop(
            object_name=result["collection_name"],
            scene_type=location["type"],
            max_iterations=3,  # budget per location
            target_score=7.0,
        )
        if not vfl_result["passed"]:
            logger.warning("Location %s scored %.1f after %d iterations",
                location["name"], vfl_result["final_score"], vfl_result["iterations"])

# In compose_interior:
for room in interior_spec["rooms"]:
    result = await generate_room(room)
    # NEW: visual feedback loop per room
    vfl_result = await visual_feedback_loop(
        object_name=result["room_name"],
        scene_type="interior",
        max_iterations=4,
        target_score=7.0,
    )
```

---

## 10. Real-Time Visual Monitoring

### 10.1 Progressive Generation Monitoring

For long operations (settlement generation, dungeon layout), we add **checkpoint screenshots**:

```python
async def monitored_generation(generator_func, blender, budget):
    """Wrap a generator function with periodic visual checks.

    Every N objects generated, capture a quick viewport screenshot
    and run Tier 1 analysis. If quality drops below threshold,
    pause generation and apply fixes before continuing.
    """
    checkpoint_interval = 5  # check every 5 objects

    async for i, obj in enumerate(generator_func()):
        if i > 0 and i % checkpoint_interval == 0:
            screenshot = await blender.capture_viewport_bytes()
            tier1 = analyze_render_image_from_bytes(screenshot)

            if tier1["score"] < 40:
                logger.warning("Quality dropped to %.1f at object %d, pausing for fix",
                    tier1["score"], i)
                # Apply emergency fixes before continuing
                await apply_tier1_fixes(tier1["issues"], blender)
```

### 10.2 Early Abort

```python
async def should_abort_early(screenshot_bytes: bytes) -> tuple[bool, str]:
    """Check if generation has gone badly wrong and should restart.

    Detects:
    - Completely black viewport (generation crashed)
    - Completely white/gray viewport (nothing generated)
    - Extreme poly count spike (infinite loop in generator)
    - All objects at origin (placement logic broken)
    """
```

### 10.3 Viewport Streaming (Future)

A WebSocket-based viewport streaming system is architecturally possible but not recommended for v1:
- Blender's viewport updates are not designed for streaming
- The overhead of continuous frame capture would slow generation
- Checkpoint-based monitoring (every N objects) provides 90% of the value at 1% of the cost

**Recommendation:** Implement checkpoint monitoring for v1. Consider viewport streaming only if real-time demonstration to users becomes a requirement.

---

## 11. Implementation Plan

### Phase 1: Core Loop (Priority: HIGH)

**Files to create:**
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/quality_rubric.py` -- Rubric definitions, scoring weights, dimension configs
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/issue_mapper.py` -- Issue-to-fix mapping with MCP action templates
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/iteration_budget.py` -- Budget tracking, convergence detection
- `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/visual_feedback_loop.py` -- Main orchestrator

**Files to extend:**
- `visual_validation.py` -- Add palette compliance, ground contact, silhouette checks
- `gemini_client.py` -- Add `GeminiQualityReviewer` with rubric prompts, batching, comparison
- `blender_server.py` -- Add `visual_feedback_loop` and `targeted_capture` actions

**Estimated effort:** 2-3 phases

### Phase 2: Integration (Priority: HIGH)

- Wire GVF loop into `compose_map`, `compose_interior`, `blender_worldbuilding`
- Add checkpoint monitoring to long-running generators
- Build few-shot calibration image library

**Estimated effort:** 1-2 phases

### Phase 3: Optimization (Priority: MEDIUM)

- Response caching for similar scenes (hash contact sheets, reuse scores)
- Batch multiple scenes into single Gemini calls
- A/B testing different rubric prompts for scoring consistency
- Build regression test suite with known-good/known-bad scenes

**Estimated effort:** 1 phase

### Phase 4: Advanced (Priority: LOW)

- Style transfer suggestions ("make this more Gothic")
- Cross-scene consistency checking (all buildings in a settlement match)
- Player-facing quality telemetry (did players notice the AI-fixed scenes?)
- Viewport streaming for real-time demos

**Estimated effort:** 2+ phases

---

## 12. Testing Strategy

### 12.1 Unit Tests

```python
# Test rubric scoring with known images
def test_rubric_perfect_score():
    """AAA reference image should score >= 8.0 overall."""

def test_rubric_default_material_detection():
    """Gray-only image should fail material_quality dimension."""

def test_rubric_floating_objects():
    """Image with gap below objects should fail prop_placement."""

# Test issue mapper
def test_issue_to_fix_mapping():
    """Every known issue type should map to at least one MCP action."""

def test_fix_priority_ordering():
    """Structural fixes should come before cosmetic fixes."""

# Test budget
def test_budget_exhaustion():
    """Loop should terminate when max_iterations reached."""

def test_convergence_detection():
    """Loop should terminate when score improvement < threshold."""
```

### 12.2 Integration Tests

```python
# Test full GVF loop with mock Blender
async def test_gvf_loop_converges():
    """Generate a simple room, run GVF loop, verify score improves."""

async def test_gvf_loop_regenerates_on_failure():
    """Generate with bad seed, verify loop triggers regeneration."""

async def test_gvf_loop_respects_budget():
    """Run GVF on hard scene, verify it stops at max_iterations."""
```

### 12.3 Calibration Tests

```python
# Test Gemini scoring consistency
async def test_gemini_scoring_stability():
    """Same image scored 5 times should have stddev < 1.0."""

async def test_gemini_ranking_correctness():
    """Known-good scene should score higher than known-bad scene."""
```

---

## 13. Cost Summary

| Operation | Cost | Time | Notes |
|-----------|------|------|-------|
| Tier 1 check (10 angles) | $0 | 100ms | Local PIL analysis |
| Tier 2 check (mesh queries) | $0 | 500ms | Blender-side |
| Tier 3 check (Gemini) | $0.006 | 2-3s | Gemini 3 Flash |
| Full GVF loop (5 iterations) | $0.018 | 15-30s | Typically 1-2 Gemini calls |
| Settlement (10 buildings) | $0.18 | 3-5 min | 10 GVF loops |
| Full map review | $0.05 | 30s | 3 batched Gemini calls |
| **Daily session (100 scenes)** | **$1.80** | **~30 min** | Well within budget |

---

## 14. Key Design Decisions

1. **Gemini over Claude for review:** The VeilBreakers MCP tools run inside Claude's context. Using Claude to review its own output creates a recursion problem. Gemini provides an independent second opinion at low cost.

2. **Three tiers, not one:** Running Gemini on every screenshot wastes money and time. Tier 1 catches 60%+ of issues for free. Tier 2 catches structural issues. Tier 3 is only for semantic judgment.

3. **5 iteration cap:** Diminishing returns set in fast. If 5 rounds of fixes cannot get a scene to 7.0, the generation approach needs changing, not more patches.

4. **Fix mapping, not free-form code generation:** The issue mapper uses pre-built fix templates, not arbitrary Blender code. This is safer, faster, and more deterministic.

5. **Contact sheets over individual images:** Packing 6 angles into one image reduces Gemini API calls and gives the model spatial context across angles simultaneously.

6. **Regenerate vs fix threshold:** Below score 30, it is cheaper to regenerate with a different seed than to attempt repairs. This prevents the loop from wasting time on hopeless generations.

---

## Sources

- [GPT-4V(ision) is a Human-Aligned Evaluator for Text-to-3D Generation (CVPR 2024)](https://arxiv.org/abs/2401.04092)
- [Giving Claude Code Eyes: Round-Trip Screenshot Testing](https://medium.com/@rotbart/giving-claude-code-eyes-round-trip-screenshot-testing-ce52f7dcc563)
- [Visual Feedback Loop - Agentic Coding Handbook](https://tweag.github.io/agentic-coding-handbook/WORKFLOW_VISUAL_FEEDBACK/)
- [Claude tips for 3D work - Dave Snider](https://www.davesnider.com/posts/claude-3d)
- [Gemini API Pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [How LLMs See Images (and what it really costs you)](https://medium.com/@rajeev_ratan/how-llms-see-images-and-what-it-really-costs-you-d982ab8e67ed)
- [The Procedural Content Generation Benchmark](https://arxiv.org/abs/2503.21474)
- [AI Agent Landscape 2025-2026: A Technical Deep Dive](https://tao-hpu.medium.com/ai-agent-landscape-2025-2026-a-technical-deep-dive-abda86db7ae2)
- [Screenshot-to-Code: Evaluating Claude](https://github.com/abi/screenshot-to-code/blob/main/blog/evaluating-claude.md)
- [Closed-Loop Development: How AI Agents Build Software While You Sleep](https://medium.com/@alexzanfir/closed-loop-development-how-ai-agents-build-software-while-you-sleep-6df42cd05a85)
