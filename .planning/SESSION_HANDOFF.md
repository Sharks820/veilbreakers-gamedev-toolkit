# Session Handoff -- VeilBreakers GameDev Toolkit

**Date:** 2026-03-21
**Status:** v3.0 COMPLETE -- All 24 phases finished

---

## Project State

### What This Is
The VeilBreakers MCP Toolkit -- 37 compound MCP tools (15 Blender + 22 Unity) that transform Claude into a complete AAA game development team. Built for VeilBreakers 3D, a dark fantasy action RPG (Unity 6 + Blender).

### Milestone History
- **v1.0 COMPLETE** (Phases 1-8): Foundation -- 22 tools, 86 handlers, 2,740 tests
- **v2.0 COMPLETE** (Phases 9-17): Full Unity coverage -- 37 tools, 309 actions, 7,182 tests, 135 bugs fixed
- **v3.0 COMPLETE** (Phases 18-24): AAA mesh quality + professional systems -- 37 tools, 350 actions, 8,473+ tests

### Current Numbers
- **37 MCP tools** (15 Blender + 22 Unity), **350 actions** (309 v2.0 + 41 v3.0)
- **8,473+ tests** passing (0 failures)
- **127 procedural mesh generators** across 21 categories (467 mesh tests)
- **135+ bugs** found and fixed via Codex+Gemini tri-scanner protocol
- **949-line autonomous developer skill** with visual verification system

---

## v3.0 Additions Summary

### New Unity Actions (by tool)

**unity_vfx** (+8 actions):
`create_flipbook` | `compose_vfx_graph` | `create_projectile_chain` | `create_aoe_vfx` | `create_status_effect_vfx` | `create_deep_environmental_vfx` | `create_directional_hit_vfx` | `create_boss_transition_vfx`

**unity_audio** (+8 actions):
`setup_spatial_audio` | `setup_layered_sound` | `setup_audio_event_chain` | `setup_dynamic_music` | `setup_portal_audio` | `setup_audio_lod` | `setup_vo_pipeline` | `setup_procedural_foley`

**unity_ui** (+8 actions):
`create_procedural_frame` | `create_icon_pipeline` | `create_cursor_system` | `create_tooltip_system` | `create_radial_menu` | `create_notification_system` | `create_loading_screen` | `create_ui_shaders`

**unity_qa** (+6 actions):
`compile_recovery` | `detect_conflicts` | `orchestrate_pipeline` | `list_pipeline_steps` | `validate_art_style` | `build_smoke_test`

**unity_shader** (+3 actions):
`sss_skin_shader` | `parallax_eye_shader` | `micro_detail_normal`

**unity_scene** (+2 actions):
`create_blend_tree` | `create_additive_layer`

**unity_prefab** (+1 action):
`cloth_setup`

**unity_camera** (+1 action):
`cinematic_sequence`

### New Blender Actions (documented in v3.0)

**blender_texture** (+2 actions): `delight` | `validate_palette`
**asset_pipeline** (+4 actions): `generate_weapon` | `split_character` | `fit_armor` | `render_equipment_icon`
**blender_environment** (+1 action): `add_storytelling_props`
**blender_worldbuilding** (+7 actions): `generate_location` | `generate_boss_arena` | `generate_world_graph` | `generate_linked_interior` | `generate_multi_floor_dungeon` | `generate_overrun_variant` | `generate_easter_egg`
**blender_animation**: `generate_ai_motion` fully implemented (was stub)

### Key v3.0 Files
| File | Purpose |
|------|---------|
| `shared/unity_templates/audio_middleware_templates.py` | 8 AUDM spatial audio/foley templates |
| `shared/unity_templates/vfx_mastery_templates.py` | 8 VFX3 flipbook/VFX Graph/projectile templates |
| `shared/unity_templates/ui_polish_templates.py` | 8 UIPOL frame/icon/cursor/tooltip templates |
| `shared/unity_templates/production_templates.py` | 6 PROD compile recovery/conflict/pipeline templates |
| `shared/unity_templates/animation_templates.py` | 2 ANIM3 blend tree/additive layer templates |
| `shared/unity_templates/character_templates.py` | Cloth setup + SSS/eye shader templates |
| `shared/unity_templates/cinematic_templates.py` | Timeline-based cinematic sequence template |
| `blender_addon/handlers/_combat_timing.py` | FromSoft-style combat timing data |
| `blender_addon/handlers/animation_export.py` | AI motion generation (API + procedural fallback) |

---

## Critical Context

### Bug Scan Protocol (USER IS STRICT ABOUT THIS)
After EVERY phase completion:
1. Run full test suite (`python -m pytest tests/ -q`)
2. Run Codex CLI scan (`codex exec --full-auto "scan..."`)
3. Run Gemini CLI scan (`gemini -p "scan..."`)
4. If ANY bugs found -> fix -> re-scan
5. Repeat until ALL THREE pass CLEAN
6. **NEVER stop after just 1 round if bugs were found**

### User Preferences (from memory)
- Research VeilBreakers3DCurrent game project before planning toolkit phases
- Must add Unity auto-recompile/refresh tools
- Bug scan rounds must continue until CLEAN
- User wants OPUS-level everything -- no cutting corners on quality
- User wants Codex as code reviewer, Gemini as UI/UX reviewer, Claude Opus as senior implementor
- Gemini API key is active
- All meshes must be low-lag and buildings/dungeons must be player-walkable
- Minimap must be 1:1 exact with orthographic camera render texture
- The toolkit should eliminate the need for costly external tools (ZBrush, Wwise, etc.)

### Game Knowledge
- **10 Combat Brands:** IRON, SAVAGE, SURGE, VENOM, DREAD, LEECH, GRACE, MEND, RUIN, VOID
- **6 Hybrid Brands:** BLOODIRON, RAVENOUS, CORROSIVE, TERRORFLUX, VENOMSTRIKE, NIGHTLEECH
- **4 Hero Paths:** IRONBOUND, FANGBORN, VOIDTOUCHED, UNCHAINED
- **Corruption:** 0-100% with thresholds at 25/50/75/100%
- **Engine:** Unity 6000.3.6f1, URP 17.3.0, UI Toolkit, PrimeTween (NOT DOTween)
- **Game has turn-based battle system** (BattleManager) + toolkit also supports real-time combat
- **BLAZE is NOT a real brand** -- was removed. FROST/HOLY/NATURE/SHADOW also removed.

### MCP Setup
- `vb-blender` + `vb-unity` installed at user level (all Claude sessions)
- `vb-blender` + `vb-unity` configured in VeilBreakers3DCurrent/.mcp.json
- `UNITY_PROJECT_PATH` = `C:/Users/Conner/OneDrive/Documents/VeilBreakers3DCurrent`
- `desktop-commander` MCP installed at user level
- Gemini API key active for visual review

### Key Files
| File | Purpose |
|------|---------|
| `.claude/skills/game-developer.md` | 949-line autonomous developer skill with visual verification |
| `.planning/ROADMAP.md` | Full roadmap (v1+v2+v3) |
| `.planning/REQUIREMENTS.md` | All requirements (v1: 128, v2: 143, v3: 56) |
| `.planning/STATE.md` | Current project state |
| `.planning/research/3d-modeling-gap-analysis.md` | 67 gaps identified |
| `Tools/mcp-toolkit/blender_addon/handlers/procedural_meshes.py` | 127 mesh generators (~10,800 lines) |
| `Tools/mcp-toolkit/src/veilbreakers_mcp/unity_server.py` | 22 Unity compound tools (~9,300 lines) |
| `Tools/mcp-toolkit/src/veilbreakers_mcp/blender_server.py` | 15 Blender compound tools (~2,100 lines) |
| `Tools/mcp-toolkit/src/veilbreakers_mcp/shared/blender_client.py` | Blender TCP connection with detailed error messages |
| `Tools/mcp-toolkit/verify_tools.py` | Functional verification of all 37 tools |

### TODO Stubs Remaining
- `blender_texture action=inpaint` -- AI texture inpainting (fal.ai integration -- stub from v1.0, requires API key)

### What Codex + Gemini Said About the Roadmap
Both **APPROVED WITH ADJUSTMENTS** (adjustments were applied):
- Codex: Added AUDM-07 (dialogue/VO), AUDM-08 (procedural foley)
- Gemini: Added CHAR-08 (SSS/eye shaders), UIPOL-08 (material UI shaders)
- Both confirmed the 40%->95% AAA coverage claim is realistic

---

*Session handoff updated: 2026-03-21*
*v3.0 complete: 24 phases done, 8,473+ tests, 350 actions across 37 tools*
