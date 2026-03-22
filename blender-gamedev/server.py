"""
VeilBreakers Blender GameDev MCP Server

High-level Blender tools for rigging, animation, topology analysis,
texturing, environment generation, and export pipeline.

Communicates with Blender via socket bridge to the companion addon.
"""

import json
import socket
import struct
import tempfile
import base64
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "blender-gamedev",
    description="AI-powered Blender tools for game development: rigging, animation, topology, texturing, environments, export",
)

BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 9877  # Separate from default blender-mcp (9876)


# ---------------------------------------------------------------------------
# Blender communication
# ---------------------------------------------------------------------------

def send_to_blender(command: dict) -> dict:
    """Send a command to the Blender addon and return the response."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(120)  # 2 minute timeout for heavy operations
            sock.connect((BLENDER_HOST, BLENDER_PORT))

            data = json.dumps(command).encode("utf-8")
            sock.sendall(struct.pack("!I", len(data)))
            sock.sendall(data)

            # Read response length
            length_bytes = sock.recv(4)
            if not length_bytes:
                return {"error": "No response from Blender"}
            length = struct.unpack("!I", length_bytes)[0]

            # Read response data
            chunks = []
            received = 0
            while received < length:
                chunk = sock.recv(min(length - received, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                received += len(chunk)

            return json.loads(b"".join(chunks).decode("utf-8"))
    except ConnectionRefusedError:
        return {
            "error": "Cannot connect to Blender. Make sure Blender is running with the VeilBreakers GameDev addon enabled."
        }
    except Exception as e:
        return {"error": f"Blender communication error: {str(e)}"}


# ---------------------------------------------------------------------------
# Module A: Rigging
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_mesh_for_rigging(object_name: str) -> dict:
    """Analyze a mesh to determine rigging requirements.

    Scans mesh topology, finds potential joint locations, reports vertex count,
    symmetry quality, and problem areas that could affect rigging.

    Returns structured report: {verts, faces, symmetry_score, edge_flow_quality,
    problem_areas[], recommended_rig_template}
    """
    return send_to_blender({
        "command": "analyze_mesh_for_rigging",
        "params": {"object_name": object_name},
    })


@mcp.tool()
def create_rig_rigify(
    object_name: str,
    template: str = "humanoid",
    auto_fit: bool = True,
    symmetrize: bool = True,
) -> dict:
    """Create a Rigify-based rig fitted to a mesh.

    Templates: humanoid, quadruped, bird, insect, serpent, floating,
    dragon, multi_armed, arachnid, amorphous

    Auto-fit positions the meta-rig bones to match the mesh proportions.
    Returns bone count, hierarchy, and a screenshot of the rig overlay.
    """
    return send_to_blender({
        "command": "create_rig_rigify",
        "params": {
            "object_name": object_name,
            "template": template,
            "auto_fit": auto_fit,
            "symmetrize": symmetrize,
        },
    })


@mcp.tool()
def create_rig_creature(
    object_name: str,
    limb_count: int = 4,
    has_wings: bool = False,
    wing_type: str = "membrane",
    tail_segments: int = 0,
    extra_appendages: list[dict] | None = None,
    has_jaw: bool = True,
) -> dict:
    """Create a custom creature rig with configurable limbs.

    Builds a rig from components: spine, limbs, wings, tail, jaw, appendages.
    Each component uses best-practice constraint setups (IK, spline IK, etc.).

    wing_type: 'membrane' (bat/dragon), 'feathered' (bird), 'insect'
    extra_appendages: [{"type": "tentacle", "count": 4, "segments": 8}, ...]

    Returns rig hierarchy, constraint list, and control bone summary.
    """
    return send_to_blender({
        "command": "create_rig_creature",
        "params": {
            "object_name": object_name,
            "limb_count": limb_count,
            "has_wings": has_wings,
            "wing_type": wing_type,
            "tail_segments": tail_segments,
            "extra_appendages": extra_appendages or [],
            "has_jaw": has_jaw,
        },
    })


@mcp.tool()
def auto_weight_paint(
    mesh_name: str,
    armature_name: str,
    method: str = "heat",
    test_deformation: bool = True,
) -> dict:
    """Apply automatic weight painting and optionally test deformation.

    Methods: 'heat' (heat-based, best for organic), 'envelope' (bone envelope),
    'nearest' (nearest bone, good for mechanical)

    If test_deformation=True, automatically poses the rig at 8 standard poses
    and returns a quality score per bone group.

    Returns weight quality report with per-bone-group scores.
    """
    return send_to_blender({
        "command": "auto_weight_paint",
        "params": {
            "mesh_name": mesh_name,
            "armature_name": armature_name,
            "method": method,
            "test_deformation": test_deformation,
        },
    })


@mcp.tool()
def test_deformation(
    mesh_name: str,
    armature_name: str,
    poses: str = "standard_8",
    render_contact_sheet: bool = True,
) -> dict:
    """Test rig deformation by posing at multiple positions.

    Poses the rig at standard test poses and checks for:
    - Mesh stretching beyond threshold
    - Mesh clipping/interpenetration
    - Volume loss at joints
    - Weight bleeding between bone groups

    poses: 'standard_8' (T, A, crouch, arms-up, kick, twist, extreme-bend, rest)
           or 'custom' with custom_poses parameter

    Returns per-pose quality report + contact sheet image (base64).
    """
    return send_to_blender({
        "command": "test_deformation",
        "params": {
            "mesh_name": mesh_name,
            "armature_name": armature_name,
            "poses": poses,
            "render_contact_sheet": render_contact_sheet,
        },
    })


@mcp.tool()
def validate_rig(mesh_name: str, armature_name: str) -> dict:
    """Comprehensive rig validation.

    Checks:
    - Unweighted vertices (verts not assigned to any bone group)
    - Weight bleeding (verts assigned to wrong bones)
    - Bone roll consistency (matching rolls for symmetric bones)
    - Symmetry validation (L/R bone pairs match)
    - Hierarchy integrity (no orphan bones, proper parent chains)
    - Constraint validity (no broken targets, no cycles)
    - Deformation quality at standard poses

    Returns pass/fail per check with detailed issue descriptions.
    """
    return send_to_blender({
        "command": "validate_rig",
        "params": {
            "mesh_name": mesh_name,
            "armature_name": armature_name,
        },
    })


@mcp.tool()
def fix_weight_issues(
    mesh_name: str,
    armature_name: str,
    normalize: bool = True,
    clean_zero_weights: bool = True,
    smooth_iterations: int = 2,
) -> dict:
    """Automatically fix common weight painting issues.

    Operations:
    - Normalize all weights (ensure they sum to 1.0 per vertex)
    - Remove zero-weight vertex groups
    - Smooth weights in problem areas (detected by deformation test)
    - Fix weight bleeding between unrelated bone groups

    Returns before/after quality comparison.
    """
    return send_to_blender({
        "command": "fix_weight_issues",
        "params": {
            "mesh_name": mesh_name,
            "armature_name": armature_name,
            "normalize": normalize,
            "clean_zero_weights": clean_zero_weights,
            "smooth_iterations": smooth_iterations,
        },
    })


# ---------------------------------------------------------------------------
# Module B: Animation
# ---------------------------------------------------------------------------

@mcp.tool()
def create_walk_cycle(
    armature_name: str,
    gait_type: str = "biped",
    speed: float = 1.0,
    bounce: float = 0.5,
    stride_length: float = 1.0,
    frame_count: int = 24,
) -> dict:
    """Generate a procedural walk/run cycle.

    gait_type: 'biped', 'quadruped', 'hexapod', 'arachnid', 'serpent'
    speed: Multiplier for animation speed (1.0 = normal walk, 2.0 = run)
    bounce: Vertical bob amount (0.0 = glide, 1.0 = bouncy)
    stride_length: Distance per step cycle

    Uses mathematically-derived gait patterns (phase-offset sine waves,
    alternating tetrapod for insects, traveling sine for serpents).

    Returns animation clip data + contact sheet preview.
    """
    return send_to_blender({
        "command": "create_walk_cycle",
        "params": {
            "armature_name": armature_name,
            "gait_type": gait_type,
            "speed": speed,
            "bounce": bounce,
            "stride_length": stride_length,
            "frame_count": frame_count,
        },
    })


@mcp.tool()
def create_fly_cycle(
    armature_name: str,
    wing_frequency: float = 1.0,
    amplitude: float = 45.0,
    glide_ratio: float = 0.0,
    hover_mode: bool = False,
    frame_count: int = 30,
) -> dict:
    """Generate a flying/hovering animation cycle.

    wing_frequency: Flaps per second
    amplitude: Wing rotation range in degrees
    glide_ratio: 0.0 = constant flapping, 1.0 = mostly gliding
    hover_mode: Stationary hover with faster, smaller flaps

    Handles: wing fold/extend, body tilt, tail counterbalance, head stabilization.

    Returns animation clip data + contact sheet preview.
    """
    return send_to_blender({
        "command": "create_fly_cycle",
        "params": {
            "armature_name": armature_name,
            "wing_frequency": wing_frequency,
            "amplitude": amplitude,
            "glide_ratio": glide_ratio,
            "hover_mode": hover_mode,
            "frame_count": frame_count,
        },
    })


@mcp.tool()
def create_idle_animation(
    armature_name: str,
    breathing_intensity: float = 0.5,
    weight_shift: bool = True,
    secondary_motion: bool = True,
    frame_count: int = 60,
) -> dict:
    """Generate a natural idle animation.

    Combines: breathing (chest expand/contract), subtle weight shifting,
    and secondary motion on tails, ears, wings, tentacles.

    Returns animation clip data + contact sheet preview.
    """
    return send_to_blender({
        "command": "create_idle_animation",
        "params": {
            "armature_name": armature_name,
            "breathing_intensity": breathing_intensity,
            "weight_shift": weight_shift,
            "secondary_motion": secondary_motion,
            "frame_count": frame_count,
        },
    })


@mcp.tool()
def create_attack_animation(
    armature_name: str,
    attack_type: str = "melee_swing",
    speed: float = 1.0,
    power_level: float = 0.5,
    frame_count: int = 30,
) -> dict:
    """Generate an attack animation following animation principles.

    attack_type: 'melee_swing', 'melee_thrust', 'slam', 'bite', 'claw_swipe',
                 'tail_whip', 'wing_buffet', 'ranged_cast', 'breath_attack'
    power_level: 0.0-1.0 affects anticipation/follow-through intensity

    Uses: anticipation (wind-up), action (fast strike), follow-through (recovery)

    Returns animation clip data + contact sheet preview.
    """
    return send_to_blender({
        "command": "create_attack_animation",
        "params": {
            "armature_name": armature_name,
            "attack_type": attack_type,
            "speed": speed,
            "power_level": power_level,
            "frame_count": frame_count,
        },
    })


@mcp.tool()
def render_animation_preview(
    armature_name: str,
    action_name: str,
    format: str = "contact_sheet",
    frame_step: int = 4,
    camera_angles: list[str] | None = None,
) -> dict:
    """Render an animation preview for visual verification.

    format: 'contact_sheet' (grid of frames), 'gif' (animated)
    frame_step: Capture every Nth frame
    camera_angles: ['front', 'side', 'three_quarter', 'top'] (default: all four)

    Returns base64-encoded image(s) that can be visually inspected.
    """
    return send_to_blender({
        "command": "render_animation_preview",
        "params": {
            "armature_name": armature_name,
            "action_name": action_name,
            "format": format,
            "frame_step": frame_step,
            "camera_angles": camera_angles or ["front", "side", "three_quarter"],
        },
    })


# ---------------------------------------------------------------------------
# Module C: Topology Analysis & Repair
# ---------------------------------------------------------------------------

@mcp.tool()
def analyze_topology(object_name: str) -> dict:
    """Full mesh topology analysis with quality grading.

    Checks:
    - Non-manifold edges/vertices
    - N-gon count and locations
    - Triangle count and percentage
    - Pole locations (vertices with 5+ edges) in deformation areas
    - Edge flow quality (follows muscle/joint lines)
    - Face area consistency
    - Loose geometry (unconnected verts/edges)
    - Inverted normals
    - Zero-area faces
    - Duplicate vertices/faces

    Returns scored report card (A-F per category) with issue locations.
    """
    return send_to_blender({
        "command": "analyze_topology",
        "params": {"object_name": object_name},
    })


@mcp.tool()
def fix_topology_auto(
    object_name: str,
    remove_doubles_threshold: float = 0.0001,
    fix_normals: bool = True,
    fill_holes: bool = True,
    remove_loose: bool = True,
    dissolve_degenerate: bool = True,
) -> dict:
    """Automatically fix common topology issues.

    Operations (each can be toggled):
    - Remove duplicate vertices within threshold
    - Recalculate normals (outside)
    - Fill holes (boundary edges)
    - Remove loose vertices/edges
    - Dissolve degenerate/zero-area faces

    Returns fix count per category + before/after comparison.
    """
    return send_to_blender({
        "command": "fix_topology_auto",
        "params": {
            "object_name": object_name,
            "remove_doubles_threshold": remove_doubles_threshold,
            "fix_normals": fix_normals,
            "fill_holes": fill_holes,
            "remove_loose": remove_loose,
            "dissolve_degenerate": dissolve_degenerate,
        },
    })


@mcp.tool()
def analyze_uvs(object_name: str) -> dict:
    """Analyze UV map quality.

    Checks:
    - UV stretch (distortion from 3D to 2D mapping)
    - UV overlap (faces sharing UV space)
    - Island count and packing efficiency
    - Texel density consistency across the mesh
    - Seam placement quality (visible vs hidden areas)
    - UV bounds (anything outside 0-1 range)

    Returns UV quality score + rendered UV layout preview.
    """
    return send_to_blender({
        "command": "analyze_uvs",
        "params": {"object_name": object_name},
    })


@mcp.tool()
def check_game_ready(
    object_name: str,
    poly_budget: int = 50000,
    max_materials: int = 4,
    max_bones: int = 256,
    require_uv2: bool = False,
) -> dict:
    """Check if a mesh meets game-readiness requirements.

    Validates against configurable budgets:
    - Polygon count vs budget
    - Material/texture slot count
    - Bone count (if rigged)
    - UV map presence and quality
    - Lightmap UV (UV2) if required
    - Clean topology (no non-manifold, no loose geometry)
    - Proper naming conventions

    Returns pass/fail checklist with specific recommendations.
    """
    return send_to_blender({
        "command": "check_game_ready",
        "params": {
            "object_name": object_name,
            "poly_budget": poly_budget,
            "max_materials": max_materials,
            "max_bones": max_bones,
            "require_uv2": require_uv2,
        },
    })


# ---------------------------------------------------------------------------
# Module D: Texturing
# ---------------------------------------------------------------------------

@mcp.tool()
def create_pbr_material(
    object_name: str,
    material_description: str,
    resolution: int = 2048,
) -> dict:
    """Create a PBR material from a text description.

    Uses Blender's shader node system to build a physically-based material
    based on the description (e.g., "weathered bronze armor with green patina",
    "rough volcanic rock with glowing cracks").

    Generates: Base Color, Normal, Roughness, Metallic nodes configured
    for the described appearance.

    Returns material preview render (sphere + flat).
    """
    return send_to_blender({
        "command": "create_pbr_material",
        "params": {
            "object_name": object_name,
            "material_description": material_description,
            "resolution": resolution,
        },
    })


@mcp.tool()
def bake_textures(
    high_poly: str,
    low_poly: str,
    bake_types: list[str] | None = None,
    resolution: int = 2048,
    cage_extrusion: float = 0.01,
) -> dict:
    """Bake texture maps from high-poly to low-poly mesh.

    bake_types: ['normal', 'ao', 'curvature', 'thickness', 'diffuse', 'combined']
    Default: ['normal', 'ao']

    Automatically sets up UV, creates image textures, configures bake settings,
    and bakes all requested maps.

    Returns bake preview per map type + file paths.
    """
    return send_to_blender({
        "command": "bake_textures",
        "params": {
            "high_poly": high_poly,
            "low_poly": low_poly,
            "bake_types": bake_types or ["normal", "ao"],
            "resolution": resolution,
            "cage_extrusion": cage_extrusion,
        },
    })


# ---------------------------------------------------------------------------
# Module E: Environment Generation
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_terrain(
    style: str = "mountains",
    size: float = 100.0,
    resolution: int = 256,
    seed: int = 0,
    erosion: bool = True,
) -> dict:
    """Generate a terrain mesh.

    style: 'mountains', 'hills', 'plains', 'islands', 'volcanic', 'canyon', 'cliffs'
    size: World-space size of the terrain
    resolution: Heightmap resolution (vertices per side)
    erosion: Apply simulated erosion for realistic results

    Returns terrain preview (top-down + perspective) + stats.
    """
    return send_to_blender({
        "command": "generate_terrain",
        "params": {
            "style": style,
            "size": size,
            "resolution": resolution,
            "seed": seed,
            "erosion": erosion,
        },
    })


@mcp.tool()
def scatter_vegetation(
    terrain_name: str,
    vegetation_types: list[str] | None = None,
    density: float = 0.5,
    seed: int = 0,
) -> dict:
    """Scatter vegetation across terrain using Geometry Nodes.

    vegetation_types: ['trees', 'grass', 'rocks', 'bushes', 'flowers', 'mushrooms']
    density: 0.0-1.0 density multiplier

    Uses biome rules: slope affects placement, altitude affects type distribution.

    Returns overhead + perspective preview.
    """
    return send_to_blender({
        "command": "scatter_vegetation",
        "params": {
            "terrain_name": terrain_name,
            "vegetation_types": vegetation_types or ["trees", "grass", "rocks"],
            "density": density,
            "seed": seed,
        },
    })


# ---------------------------------------------------------------------------
# Module F: Export Pipeline
# ---------------------------------------------------------------------------

@mcp.tool()
def export_to_unity(
    object_names: list[str],
    output_path: str,
    include_animations: bool = True,
    generate_lods: bool = False,
    lod_levels: list[float] | None = None,
) -> dict:
    """Export objects to FBX with Unity-optimized settings.

    Applies Unity conventions:
    - Scale factor 1.0
    - Y-up axis conversion
    - Forward: -Z
    - Bone naming convention matching Unity Humanoid
    - Mesh triangulation

    If generate_lods=True, creates LOD variants at specified percentages.
    lod_levels default: [1.0, 0.5, 0.25, 0.1]

    Returns export report (file size, bone count, mesh stats) + validation.
    """
    return send_to_blender({
        "command": "export_to_unity",
        "params": {
            "object_names": object_names,
            "output_path": output_path,
            "include_animations": include_animations,
            "generate_lods": generate_lods,
            "lod_levels": lod_levels or [1.0, 0.5, 0.25, 0.1],
        },
    })


@mcp.tool()
def validate_export(exported_file: str) -> dict:
    """Validate an exported FBX file by re-importing and checking.

    Re-imports the file into a temporary Blender scene and validates:
    - Scale is correct (not 100x or 0.01x)
    - Orientation matches (Y-up)
    - Bone count preserved
    - Material slots preserved
    - Mesh vertex/face counts match
    - Animations present if expected

    Returns validation pass/fail with details.
    """
    return send_to_blender({
        "command": "validate_export",
        "params": {"exported_file": exported_file},
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
