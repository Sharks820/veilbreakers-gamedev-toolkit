# TERRAIN AGENT PROTOCOL — Strict Adherence Required

**Audience:** Every AI agent (Claude, Codex, Gemini, GSD subagents, human contributors)
touching terrain code on the `feature/terrain-world-foundation` branch or its
descendants.

**Authority:** This document is the operational rulebook for terrain generation
in VeilBreakers. It complements — but does NOT supersede — the authoritative
plan at `docs/terrain_ultra_implementation_plan_2026-04-08.md`. When this
document and the plan disagree, the plan wins; file a correction here.

**You are not permitted to bypass this protocol.** Violations are architectural
regressions and will be rejected in code review.

---

## 0. TL;DR — The Five Rules

1. **All mutating terrain operations route through `TerrainPassController`.**
   Never call `_terrain_erosion`, `_terrain_noise`, or any mesh builder
   directly from a new handler. If you need a new mutation, register a
   `PassDefinition`.
2. **Every mutation requires a `TerrainSceneRead`.** Passes that declare
   `requires_scene_read=True` will raise `SceneReadRequired` if the intent
   lacks one. Do not bypass this by lying about scene state.
3. **All signals live on the `TerrainMaskStack`.** If a pass computes
   slope, curvature, flow, wetness, deposition, saliency, or any other
   intermediate signal, it writes that signal to the mask stack via
   `stack.set(channel, value, pass_name)`. **Discarding intermediate
   signals is the single worst anti-pattern in this codebase.**
4. **Every pass is deterministic given the same seed.** Use
   `derive_pass_seed(...)` — never `hash()`, never `random.random()` without
   a seed, never `time.time()`.
5. **Every pass respects protected zones.** Either the orchestrator rejects
   the pass wholesale (zone fully covers target) or the pass masks out
   forbidden cells per-cell. No exceptions.

---

## 1. Required imports for terrain work

```python
from blender_addon.handlers.terrain_semantics import (
    TerrainMaskStack,
    TerrainIntentState,
    TerrainSceneRead,
    TerrainPipelineState,
    PassDefinition,
    PassResult,
    ValidationIssue,
    BBox,
    ProtectedZoneSpec,
    HeroFeatureSpec,
    SceneReadRequired,
    ProtectedZoneViolation,
    PassContractError,
)
from blender_addon.handlers.terrain_pipeline import (
    TerrainPassController,
    derive_pass_seed,
    register_default_passes,
)
from blender_addon.handlers.terrain_masks import compute_base_masks
```

If your file is in `handlers/` you use relative imports (`.terrain_semantics`).

## 2. Anatomy of a compliant pass

```python
def pass_my_feature(
    state: TerrainPipelineState,
    region: Optional[BBox],
) -> PassResult:
    """One sentence of what this pass does for terrain quality.

    Contract
    --------
    Consumes: <channels>
    Produces: <channels>
    Respects protected zones: yes/no
    Requires scene read: yes/no
    """
    t0 = time.perf_counter()
    stack = state.mask_stack
    issues: list[ValidationIssue] = []

    # 1. Verify prerequisites (orchestrator already checked, but double-check
    #    local invariants you depend on)

    # 2. Resolve region scope
    r_slice, c_slice = _region_slice(state, region)

    # 3. Build a per-cell protected mask and honor it everywhere you write
    protected = _protected_mask(state, stack.height.shape, "my_feature")

    # 4. Do the work. Never call random, time, or hash — use derive_pass_seed.
    seed = derive_pass_seed(state.intent.seed, "my_feature",
                            state.tile_x, state.tile_y, region)

    # 5. Write every intermediate signal to the mask stack
    stack.set("my_new_channel", computed_array, "my_feature")

    # 6. Return a PassResult with metrics + any issues
    return PassResult(
        pass_name="my_feature",
        status="ok" if not any(i.is_hard() for i in issues) else "failed",
        duration_seconds=time.perf_counter() - t0,
        consumed_channels=(...,),
        produced_channels=(...,),
        metrics={...},
        issues=issues,
    )
```

Then register it:

```python
TerrainPassController.register_pass(PassDefinition(
    name="my_feature",
    func=pass_my_feature,
    requires_channels=("height", "slope"),
    produces_channels=("my_new_channel",),
    seed_namespace="my_feature",
    requires_scene_read=True,
    may_modify_geometry=True,  # if the pass mutates Blender meshes
))
```

## 3. Anti-patterns (DO NOT)

| ❌ Anti-pattern | ✅ Correct approach |
|---|---|
| Call `apply_hydraulic_erosion` directly from a handler | Register a pass, call `TerrainPassController.run_pass("erosion")` |
| Return only the eroded heightmap | Return `ErosionMasks` and populate mask stack |
| Clip heights to `[0, 1]` | Keep world-unit heights; clip only for visualization |
| Use `hash(...)` or `random.random()` for seeds | Use `derive_pass_seed(...)` |
| Skip scene-read "because it's just a test" | Attach a minimal `TerrainSceneRead` in the fixture |
| Mutate the heightmap in place without recording a pass | Always go through `run_pass` |
| Add a new mask channel without updating `_ARRAY_CHANNELS` in `TerrainMaskStack` | Add the field AND the `_ARRAY_CHANNELS` tuple entry |
| Call `handle_generate_terrain_tile` from new code | Call `handle_run_terrain_pass` instead |
| Put material/color logic outside `terrain_materials.py` | Keep material zoning in its module |
| Carve cliffs by "noise + scale" | Build a real cliff anatomy (Bundle B): lip + face + ledges + talus |

## 4. Quality gates — every pass SHOULD have one

A `QualityGate` is a callable `(PassResult, TerrainMaskStack) -> list[ValidationIssue]`
that checks visual-semantic quality after the pass runs. Bundle A ships
`pass_validation_minimal` as the global gate; bundles B–N add
pass-specific gates. Register yours in `PassDefinition.quality_gate`.

Examples:
- `erosion`: wetness > 0 in at least 5% of cells; drainage distribution follows
  power law; no cell has erosion_amount > 10× median
- `cliffs`: every registered cliff has lip + face + ledges + talus present;
  protected zones have zero overlap with cliff_candidate mask
- `materials`: every biome boundary has a soft transition band; no single
  material exceeds 80% of the tile area

If your gate returns any hard `ValidationIssue`, the pass status downgrades
to `"warning"` (soft issues) or `"failed"` (hard issues), and the
orchestrator auto-rolls-back on `"failed"`.

## 5. Visual oversight — contact sheets on request

Use `blender_viewport action=contact_sheet` for multi-angle visual QA
AFTER the user asks for visual verification. Do NOT auto-screenshot after
every pass — screenshots are expensive and the user controls cadence.

For automated visual regression, use `aaa_verify_map` with explicit
`required_angle_count` and `angle_labels` (see the preserve-list tests
for the exact invocation).

## 6. Agent checklist before committing terrain work

- [ ] Did I register a new pass, or add to an existing one? (Never stuff
      two responsibilities into one pass.)
- [ ] Does my pass consume + produce declared channels?
- [ ] Did I run the pipeline smoke tests (`pytest tests/test_terrain_pipeline_smoke.py`)?
- [ ] Did I run the preserve-list tests (`pytest tests/test_preserve_list.py`)?
- [ ] Does the full suite still match baseline (`pytest tests/` — 3
      pre-existing failures, nothing new)?
- [ ] Did I update Appendix D compliance checklist for my bundle?
- [ ] Did I NOT introduce `hash()`, `random.random()`, `time.time()` for
      seeding, or `np.clip(..., 0, 1)` on world heights?
- [ ] Did I NOT bypass `TerrainPassController`?
- [ ] Did I NOT regress Codex's 7 preserve-list items?

---

## 7. When this protocol blocks you

Don't silently bypass. Open a correction PR against this file with:
- What you were trying to do
- Which rule blocked you
- Why the rule doesn't fit your case
- The alternative behavior you propose

Then continue work under the *current* rule until the correction lands.
The protocol is strict on purpose — drift kills architectural coherence.

---

_Last updated: Bundle A landing (commit f467f33)._
