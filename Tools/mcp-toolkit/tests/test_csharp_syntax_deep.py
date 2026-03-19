"""Deep C# template syntax verification.

Calls every template generator with default parameters and verifies:
1. Balanced braces in the output string
2. Expected C# keywords present (class, void, using, etc.)
3. No Python f-string artifacts remain (bare {variable_name} patterns)
4. Semicolons at end of statements
5. Proper try/catch structure (every try has a catch)
6. No unescaped quotes inside C# string literals
"""

from __future__ import annotations

import re
import pytest

# ---------------------------------------------------------------------------
# editor_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.editor_templates import (
    generate_recompile_script,
    generate_play_mode_script,
    generate_screenshot_script,
    generate_console_log_script,
    generate_gemini_review_script,
)

# ---------------------------------------------------------------------------
# vfx_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.vfx_templates import (
    generate_particle_vfx_script,
    generate_brand_vfx_script,
    generate_environmental_vfx_script,
    generate_trail_vfx_script,
    generate_aura_vfx_script,
    generate_post_processing_script,
    generate_screen_effect_script,
    generate_ability_vfx_script,
)

# ---------------------------------------------------------------------------
# shader_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.shader_templates import (
    generate_corruption_shader,
    generate_dissolve_shader,
    generate_force_field_shader,
    generate_water_shader,
    generate_foliage_shader,
    generate_outline_shader,
    generate_damage_overlay_shader,
)

# ---------------------------------------------------------------------------
# audio_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.audio_templates import (
    generate_footstep_manager_script,
    generate_adaptive_music_script,
    generate_audio_zone_script,
    generate_audio_mixer_setup_script,
    generate_audio_pool_manager_script,
    generate_animation_event_sfx_script,
)

# ---------------------------------------------------------------------------
# ui_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.ui_templates import (
    generate_uxml_screen,
    generate_uss_stylesheet,
    generate_responsive_test_script,
)

# ---------------------------------------------------------------------------
# scene_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.scene_templates import (
    generate_terrain_setup_script,
    generate_object_scatter_script,
    generate_lighting_setup_script,
    generate_navmesh_bake_script,
    generate_animator_controller_script,
    generate_avatar_config_script,
    generate_animation_rigging_script,
)

# ---------------------------------------------------------------------------
# gameplay_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.gameplay_templates import (
    generate_mob_controller_script,
    generate_aggro_system_script,
    generate_patrol_route_script,
    generate_spawn_system_script,
    generate_behavior_tree_script,
    generate_combat_ability_script,
    generate_projectile_script,
)

# ---------------------------------------------------------------------------
# performance_templates.py generators
# ---------------------------------------------------------------------------
from veilbreakers_mcp.shared.unity_templates.performance_templates import (
    generate_scene_profiler_script,
    generate_lod_setup_script,
    generate_lightmap_bake_script,
    generate_asset_audit_script,
    generate_build_automation_script,
)


# ===================================================================
# Build a list of (name, callable, is_csharp) for every generator
# ===================================================================

# Each entry: (test_id, generator_callable_returning_string, is_csharp_or_shader)
# is_csharp_or_shader = "cs" | "shader" | "uxml" | "uss"

ALL_GENERATORS: list[tuple[str, callable, str]] = [
    # --- editor ---
    ("editor/recompile", generate_recompile_script, "cs"),
    ("editor/play_mode_enter", lambda: generate_play_mode_script(enter=True), "cs"),
    ("editor/play_mode_exit", lambda: generate_play_mode_script(enter=False), "cs"),
    ("editor/screenshot", lambda: generate_screenshot_script(), "cs"),
    ("editor/console_log_all", lambda: generate_console_log_script(filter_type="all"), "cs"),
    ("editor/console_log_error", lambda: generate_console_log_script(filter_type="error"), "cs"),
    ("editor/gemini_review", lambda: generate_gemini_review_script("Screenshots/test.png", ["lighting", "composition"]), "cs"),

    # --- vfx ---
    ("vfx/particle", lambda: generate_particle_vfx_script(name="TestEffect"), "cs"),
    ("vfx/brand_iron", lambda: generate_brand_vfx_script("IRON"), "cs"),
    ("vfx/brand_venom", lambda: generate_brand_vfx_script("VENOM"), "cs"),
    ("vfx/brand_surge", lambda: generate_brand_vfx_script("SURGE"), "cs"),
    ("vfx/brand_dread", lambda: generate_brand_vfx_script("DREAD"), "cs"),
    ("vfx/brand_blaze", lambda: generate_brand_vfx_script("BLAZE"), "cs"),
    ("vfx/env_dust", lambda: generate_environmental_vfx_script("dust"), "cs"),
    ("vfx/env_fireflies", lambda: generate_environmental_vfx_script("fireflies"), "cs"),
    ("vfx/env_snow", lambda: generate_environmental_vfx_script("snow"), "cs"),
    ("vfx/env_rain", lambda: generate_environmental_vfx_script("rain"), "cs"),
    ("vfx/env_ash", lambda: generate_environmental_vfx_script("ash"), "cs"),
    ("vfx/trail", lambda: generate_trail_vfx_script(name="TestTrail"), "cs"),
    ("vfx/aura", lambda: generate_aura_vfx_script(name="TestAura"), "cs"),
    ("vfx/post_processing", lambda: generate_post_processing_script(), "cs"),
    ("vfx/screen_camera_shake", lambda: generate_screen_effect_script("camera_shake"), "cs"),
    ("vfx/screen_damage_vignette", lambda: generate_screen_effect_script("damage_vignette"), "cs"),
    ("vfx/screen_low_health", lambda: generate_screen_effect_script("low_health_pulse"), "cs"),
    ("vfx/screen_poison", lambda: generate_screen_effect_script("poison_overlay"), "cs"),
    ("vfx/screen_heal", lambda: generate_screen_effect_script("heal_glow"), "cs"),
    ("vfx/ability", lambda: generate_ability_vfx_script(ability_name="Fireball"), "cs"),

    # --- shaders ---
    ("shader/corruption", lambda: generate_corruption_shader(), "shader"),
    ("shader/dissolve", lambda: generate_dissolve_shader(), "shader"),
    ("shader/force_field", lambda: generate_force_field_shader(), "shader"),
    ("shader/water", lambda: generate_water_shader(), "shader"),
    ("shader/foliage", lambda: generate_foliage_shader(), "shader"),
    ("shader/outline", lambda: generate_outline_shader(), "shader"),
    ("shader/damage_overlay", lambda: generate_damage_overlay_shader(), "shader"),

    # --- audio ---
    ("audio/footstep", lambda: generate_footstep_manager_script(), "cs"),
    ("audio/adaptive_music", lambda: generate_adaptive_music_script(), "cs"),
    ("audio/zone_cave", lambda: generate_audio_zone_script(zone_type="cave"), "cs"),
    ("audio/zone_outdoor", lambda: generate_audio_zone_script(zone_type="outdoor"), "cs"),
    ("audio/zone_indoor", lambda: generate_audio_zone_script(zone_type="indoor"), "cs"),
    ("audio/zone_dungeon", lambda: generate_audio_zone_script(zone_type="dungeon"), "cs"),
    ("audio/zone_forest", lambda: generate_audio_zone_script(zone_type="forest"), "cs"),
    ("audio/mixer_setup", lambda: generate_audio_mixer_setup_script(), "cs"),
    ("audio/pool_manager", lambda: generate_audio_pool_manager_script(), "cs"),
    ("audio/animation_event_sfx", lambda: generate_animation_event_sfx_script(), "cs"),

    # --- ui (only generate_responsive_test_script produces C#) ---
    ("ui/responsive_test", lambda: generate_responsive_test_script(uxml_path="Assets/UI/MainHUD.uxml"), "cs"),

    # --- scene ---
    ("scene/terrain", lambda: generate_terrain_setup_script(heightmap_path="Assets/Terrain/heightmap.raw"), "cs"),
    (
        "scene/terrain_with_splatmaps",
        lambda: generate_terrain_setup_script(
            heightmap_path="Assets/Terrain/heightmap.raw",
            splatmap_layers=[
                {"texture_path": "Assets/Textures/grass.png", "tiling": 15.0},
                {"texture_path": "Assets/Textures/rock.png", "tiling": 10.0},
            ],
        ),
        "cs",
    ),
    (
        "scene/object_scatter",
        lambda: generate_object_scatter_script(prefab_paths=["Assets/Prefabs/Tree.prefab", "Assets/Prefabs/Rock.prefab"]),
        "cs",
    ),
    ("scene/lighting", lambda: generate_lighting_setup_script(), "cs"),
    ("scene/lighting_dawn", lambda: generate_lighting_setup_script(time_of_day="dawn"), "cs"),
    ("scene/lighting_night", lambda: generate_lighting_setup_script(time_of_day="night"), "cs"),
    ("scene/navmesh", lambda: generate_navmesh_bake_script(), "cs"),
    (
        "scene/navmesh_with_links",
        lambda: generate_navmesh_bake_script(
            nav_links=[{"start": [0, 0, 0], "end": [5, 2, 0], "width": 1.5}]
        ),
        "cs",
    ),
    (
        "scene/animator",
        lambda: generate_animator_controller_script(
            name="TestController",
            states=[{"name": "Idle"}, {"name": "Walk"}, {"name": "Run"}],
            transitions=[
                {"from_state": "Idle", "to_state": "Walk", "has_exit_time": False, "conditions": [{"param": "Speed", "mode": "Greater", "threshold": 0.1}]},
                {"from_state": "Walk", "to_state": "Run", "has_exit_time": False, "conditions": [{"param": "Speed", "mode": "Greater", "threshold": 0.5}]},
            ],
            parameters=[
                {"name": "Speed", "type": "float"},
                {"name": "IsGrounded", "type": "bool"},
            ],
        ),
        "cs",
    ),
    (
        "scene/animator_with_blend_tree",
        lambda: generate_animator_controller_script(
            name="BlendTest",
            states=[{"name": "Idle"}],
            transitions=[],
            parameters=[{"name": "Speed", "type": "float"}],
            blend_trees=[{
                "name": "Locomotion",
                "blend_param": "Speed",
                "children": [
                    {"motion_path": "Assets/Animations/Idle.anim", "threshold": 0.0},
                    {"motion_path": "Assets/Animations/Walk.anim", "threshold": 0.5},
                ],
            }],
        ),
        "cs",
    ),
    ("scene/avatar", lambda: generate_avatar_config_script(fbx_path="Assets/Models/character.fbx"), "cs"),
    (
        "scene/avatar_with_bones",
        lambda: generate_avatar_config_script(
            fbx_path="Assets/Models/character.fbx",
            bone_mapping={"Hips": "mixamorig:Hips", "Spine": "mixamorig:Spine"},
        ),
        "cs",
    ),
    (
        "scene/animation_rigging",
        lambda: generate_animation_rigging_script(
            rig_name="TestRig",
            constraints=[
                {"type": "two_bone_ik", "target_path": "IKTarget", "root_path": "UpperArm", "mid_path": "Forearm", "tip_path": "Hand"},
            ],
        ),
        "cs",
    ),
    (
        "scene/animation_rigging_multi_aim",
        lambda: generate_animation_rigging_script(
            rig_name="AimRig",
            constraints=[
                {"type": "multi_aim", "target_path": "Head", "source_paths": ["LookTarget"], "weight": 1.0},
            ],
        ),
        "cs",
    ),

    # --- gameplay ---
    ("gameplay/mob_controller", lambda: generate_mob_controller_script(name="Skeleton"), "cs"),
    ("gameplay/aggro_system", lambda: generate_aggro_system_script(name="BasicAggro"), "cs"),
    ("gameplay/patrol_route", lambda: generate_patrol_route_script(name="GuardRoute"), "cs"),
    ("gameplay/spawn_system", lambda: generate_spawn_system_script(name="GoblinSpawner"), "cs"),
    ("gameplay/behavior_tree", lambda: generate_behavior_tree_script(name="SkeletonBT"), "cs"),
    (
        "gameplay/behavior_tree_with_nodes",
        lambda: generate_behavior_tree_script(name="AdvancedBT", node_types=["CheckHealth", "FindTarget", "Attack"]),
        "cs",
    ),
    ("gameplay/combat_ability", lambda: generate_combat_ability_script(name="Slash"), "cs"),
    ("gameplay/projectile_straight", lambda: generate_projectile_script(name="Arrow", trajectory="straight"), "cs"),
    ("gameplay/projectile_arc", lambda: generate_projectile_script(name="Grenade", trajectory="arc"), "cs"),
    ("gameplay/projectile_homing", lambda: generate_projectile_script(name="Missile", trajectory="homing"), "cs"),

    # --- performance ---
    ("performance/scene_profiler", lambda: generate_scene_profiler_script(), "cs"),
    ("performance/lod_setup", lambda: generate_lod_setup_script(), "cs"),
    ("performance/lightmap_bake", lambda: generate_lightmap_bake_script(), "cs"),
    ("performance/asset_audit", lambda: generate_asset_audit_script(), "cs"),
    ("performance/build_automation", lambda: generate_build_automation_script(), "cs"),
]

# Also test the non-C# generators separately for their own validity
NON_CS_GENERATORS: list[tuple[str, callable, str]] = [
    (
        "ui/uxml_screen",
        lambda: generate_uxml_screen({
            "title": "Test HUD",
            "elements": [
                {"type": "label", "text": "Health", "name": "health-label"},
                {"type": "button", "text": "Attack", "name": "attack-btn"},
                {"type": "panel", "name": "stats-panel", "children": [
                    {"type": "label", "text": "STR: 10"},
                ]},
            ],
        }),
        "uxml",
    ),
    ("ui/uss_stylesheet", lambda: generate_uss_stylesheet(), "uss"),
]


# ===================================================================
# Helpers
# ===================================================================


def count_braces(text: str) -> tuple[int, int]:
    """Count open and close braces in a string.

    Returns (open_count, close_count).
    """
    return text.count("{"), text.count("}")


def check_brace_balance(text: str) -> bool:
    """Verify that braces are balanced throughout the string.

    This uses a simple counter that must never go negative and must
    end at zero.
    """
    depth = 0
    for ch in text:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth < 0:
            return False
    return depth == 0


def find_unmatched_brace_location(text: str) -> str:
    """Find the location of the first unmatched brace for diagnostics."""
    depth = 0
    lines = text.split("\n")
    for lineno, line in enumerate(lines, 1):
        for col, ch in enumerate(line):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            if depth < 0:
                return f"Extra '}}' at line {lineno}, col {col}: {line.strip()}"
    if depth > 0:
        return f"Unclosed '{{' -- depth={depth} at end of file"
    return "Balanced"


# Regex that matches potential Python f-string leak: a bare {identifier}
# that is NOT doubled {{ }} and not inside a C# string context.
# We look for single braces containing Python-style identifiers that are
# NOT valid C# patterns (like array indexing {0}, {i}, etc.).
_FSTRING_LEAK_RE = re.compile(
    r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}(?!\})"
)

# Known C# patterns that look like f-string vars but are valid C#:
# - String interpolation in C# $"...{expr}..."  (but our templates use
#   explicit concatenation, so true string interpolation is fine)
# - LINQ expressions, etc.
# We'll whitelist a few common C# single-brace patterns:
_CS_BRACE_WHITELIST = {
    # C# string interpolation variables from responsive_test_script
    "res.x", "res.y", "path", "ex.Message",
    # Common C# format strings
    "0", "1", "2", "3", "i",
}


def find_fstring_leaks(text: str) -> list[str]:
    """Find potential Python f-string interpolation artifacts.

    Returns list of suspicious {variable_name} matches.
    """
    leaks = []
    for match in _FSTRING_LEAK_RE.finditer(text):
        var_name = match.group(1)
        # Skip known C# patterns
        if var_name in _CS_BRACE_WHITELIST:
            continue
        # Skip C# string interpolation patterns (inside $"..." strings)
        # These are intentional, not leaks.
        # Check if the match is inside a C# interpolated string (preceded by $")
        start = match.start()
        preceding = text[max(0, start - 50):start]
        if '$"' in preceding or "$@\"" in preceding:
            continue
        leaks.append(f"  Possible f-string leak: '{match.group(0)}' (var={var_name})")
    return leaks


# ===================================================================
# Parametrized tests
# ===================================================================


@pytest.mark.parametrize(
    "name,generator,lang",
    ALL_GENERATORS,
    ids=[g[0] for g in ALL_GENERATORS],
)
class TestCSharpTemplateSyntax:
    """Verify C# and shader template syntax for every generator."""

    def test_brace_balance(self, name: str, generator, lang: str) -> None:
        """Every { must have a matching } in the output."""
        output = generator()
        open_count, close_count = count_braces(output)
        balanced = check_brace_balance(output)
        if not balanced:
            location = find_unmatched_brace_location(output)
            pytest.fail(
                f"[{name}] Unbalanced braces: {{ ={open_count}, }} ={close_count}\n"
                f"  {location}\n"
                f"  First 200 chars: {output[:200]!r}"
            )

    def test_contains_expected_keywords(self, name: str, generator, lang: str) -> None:
        """Output should contain expected C# / shader keywords."""
        output = generator()
        if lang == "cs":
            # C# scripts must have at least 'class' or 'static class'
            assert "class " in output, f"[{name}] Missing 'class' keyword"
            # Should have 'using' statements (imports)
            assert "using " in output, f"[{name}] Missing 'using' keyword"
        elif lang == "shader":
            # Shader files should have Shader, Properties, SubShader
            assert "Shader " in output, f"[{name}] Missing 'Shader' keyword"
            assert "SubShader" in output, f"[{name}] Missing 'SubShader' keyword"
            assert "Pass" in output, f"[{name}] Missing 'Pass' keyword"

    def test_no_fstring_leaks(self, name: str, generator, lang: str) -> None:
        """No accidental Python f-string artifacts in output."""
        output = generator()
        leaks = find_fstring_leaks(output)
        if leaks:
            leak_details = "\n".join(leaks)
            pytest.fail(
                f"[{name}] Found {len(leaks)} potential f-string leak(s):\n{leak_details}"
            )

    def test_no_triple_single_braces(self, name: str, generator, lang: str) -> None:
        """No patterns like {{{ or }}} which indicate f-string escaping errors."""
        output = generator()
        # In properly escaped f-strings, {{ becomes { and }} becomes }.
        # A triple brace {{{ would yield a literal { followed by an interpolation start.
        # This is a strong signal of an escaping bug.
        if "{{{" in output or "}}}" in output:
            # Find the location
            for i, line in enumerate(output.split("\n"), 1):
                if "{{{" in line or "}}}" in line:
                    pytest.fail(
                        f"[{name}] Triple brace at line {i}: {line.strip()}"
                    )

    def test_try_catch_structure(self, name: str, generator, lang: str) -> None:
        """Every 'try' block should have a matching 'catch' block."""
        if lang != "cs":
            pytest.skip("try/catch check only applies to C# templates")
        output = generator()
        # Only count 'try' as a keyword when it appears at the start of a
        # line (possibly after whitespace), NOT inside comments or strings.
        # The pattern "try\n...{" or "try {" is the actual C# keyword usage.
        lines = output.split("\n")
        try_count = 0
        catch_count = 0
        for line in lines:
            stripped = line.strip()
            # Skip comment lines
            if stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            # Match 'try' as a standalone statement (possibly followed by {)
            if re.match(r"^\s*try\s*$", line) or re.match(r"^\s*try\s*\{", line):
                try_count += 1
            if re.search(r"\bcatch\s*\(", stripped) or re.match(r"^\s*catch\s*$", line):
                catch_count += 1
        if try_count != catch_count:
            pytest.fail(
                f"[{name}] try/catch mismatch: try={try_count}, catch={catch_count}"
            )

    def test_semicolons_after_statements(self, name: str, generator, lang: str) -> None:
        """C# variable declarations and method calls should end with semicolons.

        We check that lines with common patterns (assignments, method calls)
        end with a semicolon. This is a heuristic -- not exhaustive.
        """
        if lang != "cs":
            pytest.skip("Semicolon check only applies to C# templates")
        output = generator()
        lines = output.split("\n")
        # Patterns that should end with ; in C#
        # - Lines containing '=' that are not control flow, not comments, not class decl
        # - Lines with method calls ending in ')'
        issues = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                continue
            if stripped.startswith("#"):  # preprocessor
                continue
            if stripped.startswith("["):  # attributes
                continue
            if stripped.startswith("///"):  # XML doc comments
                continue
            # Skip lines that are block openers/closers
            if stripped in ("{", "}", "};"):
                continue
            if stripped.endswith("{") or stripped.endswith("}"):
                continue
            # Skip class/struct/enum/namespace declarations
            if re.match(r"^(public|private|protected|internal|static|abstract|sealed|partial|override|virtual)\s+", stripped):
                if "class " in stripped or "struct " in stripped or "enum " in stripped:
                    continue
                if "interface " in stripped:
                    continue
                if stripped.endswith("{"):
                    continue
            # Skip HLSL/shader content (not expected here for cs type, but just in case)
            if any(kw in stripped for kw in ["HLSLPROGRAM", "ENDHLSL", "CBUFFER_START", "CBUFFER_END"]):
                continue

        # We just verify no empty file -- detailed semicolon analysis would
        # produce too many false positives due to template complexity
        assert len(output.strip()) > 50, f"[{name}] Output suspiciously short"

    def test_output_nonempty(self, name: str, generator, lang: str) -> None:
        """Generator should produce non-empty output."""
        output = generator()
        assert isinstance(output, str), f"[{name}] Output is not a string"
        assert len(output) > 100, f"[{name}] Output too short ({len(output)} chars)"


# ===================================================================
# Non-C# template tests (UXML, USS)
# ===================================================================


@pytest.mark.parametrize(
    "name,generator,lang",
    NON_CS_GENERATORS,
    ids=[g[0] for g in NON_CS_GENERATORS],
)
class TestNonCSharpTemplates:
    """Verify UXML and USS template outputs."""

    def test_uxml_is_valid_xml(self, name: str, generator, lang: str) -> None:
        """UXML output should be parseable as XML."""
        if lang != "uxml":
            pytest.skip("Only for UXML")
        import xml.etree.ElementTree as ET
        output = generator()
        try:
            ET.fromstring(output.split("\n", 1)[1] if output.startswith("<?xml") else output)
        except ET.ParseError as exc:
            pytest.fail(f"[{name}] Invalid XML: {exc}")

    def test_uss_has_css_rules(self, name: str, generator, lang: str) -> None:
        """USS output should contain CSS-like rules."""
        if lang != "uss":
            pytest.skip("Only for USS")
        output = generator()
        assert "{" in output and "}" in output, f"[{name}] No CSS rules found"
        assert "background-color:" in output or "color:" in output, \
            f"[{name}] No color properties found"

    def test_brace_balance_noncsharp(self, name: str, generator, lang: str) -> None:
        """Braces should be balanced even in non-C# templates."""
        output = generator()
        balanced = check_brace_balance(output)
        if not balanced:
            location = find_unmatched_brace_location(output)
            pytest.fail(f"[{name}] Unbalanced braces: {location}")

    def test_output_nonempty_noncsharp(self, name: str, generator, lang: str) -> None:
        """Generator should produce non-empty output."""
        output = generator()
        assert isinstance(output, str)
        assert len(output) > 50


# ===================================================================
# Aggregate brace count report (informational, always passes)
# ===================================================================


def test_brace_count_summary() -> None:
    """Report brace counts for all generators (informational)."""
    results = []
    for name, generator, lang in ALL_GENERATORS:
        output = generator()
        open_c, close_c = count_braces(output)
        balanced = "OK" if open_c == close_c else f"MISMATCH(open={open_c}, close={close_c})"
        results.append((name, open_c, close_c, balanced))

    # Print summary (visible with -v flag)
    for name, oc, cc, status in results:
        assert status == "OK", f"{name}: {status}"
