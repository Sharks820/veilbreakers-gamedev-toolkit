# Gaps Found by Terminal 3 (Unity VFX & Content)

## Gaps in Other Terminals' Files

### T4 (Unity Systems): shader_templates.py
- The generic `VB_Dissolve` shader in shader_templates.py does not support brand-colored edge glow. T3 created a separate `VB_EvolutionDissolve` shader inline in evolution_templates.py to avoid collision, but T4 should consider adding brand color support to the generic dissolve shader for wider use.

### T2 (Animation): _combat_timing.py
- The `vfx_frames` (list[int]) field for multi-hit attacks is documented in the interface contract but may not yet be implemented in T2's combat timing handler. T3's combo VFX system checks for `vfx_frames` first and falls back to `[vfx_frame]`, but T2 should add the multi-hit frame list to their timing data.

### T1/T2 (Blender): Animation export
- Animation clips exported from Blender should follow the naming convention `{creature}_{gait}_{speed}` for T3's AnimatorController templates to auto-wire correctly. This convention is documented but not enforced at export time.

### T4 (Unity Systems): game_templates.py
- The game_templates.py `health_system` and `damage_types` actions don't emit brand-specific damage events that T3's BrandDeathController can listen to. T3 uses `OnDeath(string brand)` but there's no bridge from T4's damage system to trigger brand-specific deaths.

### General: VFX Graph Assets
- Multiple existing VFX generators in vfx_templates.py use `VisualEffect` component without assigning a `VisualEffectAsset`. T3's new systems use `ParticleSystem` instead to avoid this issue, but the pre-existing VFX-01 through VFX-05 generators still have this problem. This is documented in the audit appendix (FIX: VisualEffect Without VisualEffectAsset) but applies to T3's existing code.

## Notes
- T3 created all new systems in separate files (evolution_templates.py, combat_vfx_templates.py, action_cinematic_templates.py, animation_extensions_templates.py) to avoid merge conflicts with other terminals editing shared files.
- Brand colors are now canonical in vfx_templates.py as BRAND_PRIMARY_COLORS, BRAND_GLOW_COLORS, BRAND_DARK_COLORS. Other terminals should import from there rather than defining their own color palettes.
