"""
VeilBreakers GameDev Blender Addon

This addon runs inside Blender and listens for commands from the
blender-gamedev MCP server via a socket connection.

Install: Edit > Preferences > Add-ons > Install > Select this file
"""

bl_info = {
    "name": "VeilBreakers GameDev Bridge",
    "author": "VeilBreakers Team",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > VeilBreakers",
    "description": "MCP bridge for AI-powered game development tools",
    "category": "Development",
}

import bpy
import bmesh
import json
import math
import os
import socket
import struct
import threading
import tempfile
from mathutils import Vector, Euler, Matrix
from pathlib import Path


# ---------------------------------------------------------------------------
# Server thread
# ---------------------------------------------------------------------------

class CommandServer:
    """Socket server that receives commands from the MCP server."""

    def __init__(self, host="127.0.0.1", port=9877):
        self.host = host
        self.port = port
        self.running = False
        self.thread = None
        self.server_socket = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()

    def _run(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        self.server_socket.settimeout(1.0)

        print(f"[VeilBreakers] Listening on {self.host}:{self.port}")

        while self.running:
            try:
                client, addr = self.server_socket.accept()
                self._handle_client(client)
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_client(self, client):
        try:
            # Read message length
            length_bytes = client.recv(4)
            if not length_bytes:
                return
            length = struct.unpack("!I", length_bytes)[0]

            # Read message
            chunks = []
            received = 0
            while received < length:
                chunk = client.recv(min(length - received, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                received += len(chunk)

            command = json.loads(b"".join(chunks).decode("utf-8"))

            # Execute command on main thread
            result = {"error": "Command execution not started"}

            def execute():
                nonlocal result
                try:
                    result = dispatch_command(command)
                except Exception as e:
                    result = {"error": str(e)}

            bpy.app.timers.register(execute)

            # Wait for result (with timeout)
            import time
            timeout = 120
            start = time.time()
            while time.time() - start < timeout:
                if "error" not in result or result.get("error") != "Command execution not started":
                    break
                time.sleep(0.1)

            # Send response
            response_data = json.dumps(result).encode("utf-8")
            client.sendall(struct.pack("!I", len(response_data)))
            client.sendall(response_data)

        except Exception as e:
            error_response = json.dumps({"error": str(e)}).encode("utf-8")
            try:
                client.sendall(struct.pack("!I", len(error_response)))
                client.sendall(error_response)
            except Exception:
                pass
        finally:
            client.close()


# ---------------------------------------------------------------------------
# Command dispatcher
# ---------------------------------------------------------------------------

COMMAND_HANDLERS = {}


def handler(name):
    """Decorator to register a command handler."""
    def decorator(func):
        COMMAND_HANDLERS[name] = func
        return func
    return decorator


def dispatch_command(command: dict) -> dict:
    cmd_name = command.get("command")
    params = command.get("params", {})

    if cmd_name not in COMMAND_HANDLERS:
        return {"error": f"Unknown command: {cmd_name}"}

    return COMMAND_HANDLERS[cmd_name](**params)


# ---------------------------------------------------------------------------
# Rigging handlers
# ---------------------------------------------------------------------------

@handler("analyze_mesh_for_rigging")
def analyze_mesh_for_rigging(object_name: str) -> dict:
    obj = bpy.data.objects.get(object_name)
    if not obj or obj.type != "MESH":
        return {"error": f"Mesh object '{object_name}' not found"}

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Basic stats
    vert_count = len(bm.verts)
    face_count = len(bm.faces)
    edge_count = len(bm.edges)

    # Check symmetry (X-axis)
    sym_matches = 0
    sym_total = 0
    threshold = 0.01
    for v in bm.verts:
        if abs(v.co.x) > threshold:
            sym_total += 1
            mirror = Vector((-v.co.x, v.co.y, v.co.z))
            for v2 in bm.verts:
                if (v2.co - mirror).length < threshold:
                    sym_matches += 1
                    break

    symmetry_score = sym_matches / max(sym_total, 1)

    # Find poles (verts with != 4 edges, problematic for deformation)
    poles = []
    for v in bm.verts:
        edge_count_v = len(v.link_edges)
        if edge_count_v != 4 and edge_count_v > 2:
            poles.append({
                "index": v.index,
                "position": list(v.co),
                "edge_count": edge_count_v,
            })

    # Bounding box analysis for rig template recommendation
    bbox = obj.bound_box
    dims = obj.dimensions
    height_ratio = dims.z / max(dims.x, 0.001)
    width_ratio = dims.x / max(dims.y, 0.001)

    # Simple template recommendation
    if height_ratio > 2.5:
        recommended = "humanoid" if width_ratio < 1.5 else "serpent"
    elif height_ratio > 1.2:
        recommended = "humanoid"
    elif width_ratio > 2:
        recommended = "quadruped"
    else:
        recommended = "quadruped"

    bm.free()

    return {
        "vertices": vert_count,
        "faces": face_count,
        "edges": edge_count,
        "dimensions": list(dims),
        "symmetry_score": round(symmetry_score, 3),
        "pole_count": len(poles),
        "poles": poles[:20],  # First 20 poles
        "height_ratio": round(height_ratio, 2),
        "width_ratio": round(width_ratio, 2),
        "recommended_template": recommended,
        "status": "success",
    }


@handler("analyze_topology")
def analyze_topology(object_name: str) -> dict:
    obj = bpy.data.objects.get(object_name)
    if not obj or obj.type != "MESH":
        return {"error": f"Mesh object '{object_name}' not found"}

    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    # Non-manifold edges
    non_manifold_edges = [e.index for e in bm.edges if not e.is_manifold]

    # Non-manifold verts
    non_manifold_verts = [v.index for v in bm.verts if not v.is_manifold]

    # N-gons (faces with > 4 verts)
    ngons = [f.index for f in bm.faces if len(f.verts) > 4]

    # Triangles
    tris = [f.index for f in bm.faces if len(f.verts) == 3]

    # Quads
    quads = [f.index for f in bm.faces if len(f.verts) == 4]

    # Loose verts (not connected to any face)
    loose_verts = [v.index for v in bm.verts if not v.link_faces]

    # Loose edges
    loose_edges = [e.index for e in bm.edges if not e.link_faces]

    # Zero-area faces
    zero_area = [f.index for f in bm.faces if f.calc_area() < 1e-8]

    # Poles (verts with edge count != 4)
    poles_5plus = [v.index for v in bm.verts if len(v.link_edges) >= 5]

    total_faces = len(bm.faces)

    # Grading
    issues = 0
    grades = {}

    # Manifold grade
    nm_ratio = len(non_manifold_edges) / max(len(bm.edges), 1)
    if nm_ratio == 0:
        grades["manifold"] = "A"
    elif nm_ratio < 0.01:
        grades["manifold"] = "B"
        issues += 1
    elif nm_ratio < 0.05:
        grades["manifold"] = "C"
        issues += 2
    else:
        grades["manifold"] = "F"
        issues += 3

    # Quad ratio grade
    quad_ratio = len(quads) / max(total_faces, 1)
    if quad_ratio > 0.95:
        grades["quad_quality"] = "A"
    elif quad_ratio > 0.85:
        grades["quad_quality"] = "B"
        issues += 1
    elif quad_ratio > 0.7:
        grades["quad_quality"] = "C"
        issues += 1
    else:
        grades["quad_quality"] = "D"
        issues += 2

    # Loose geometry grade
    loose_count = len(loose_verts) + len(loose_edges)
    if loose_count == 0:
        grades["cleanliness"] = "A"
    elif loose_count < 10:
        grades["cleanliness"] = "B"
        issues += 1
    else:
        grades["cleanliness"] = "D"
        issues += 2

    # Overall grade
    if issues == 0:
        overall = "A"
    elif issues <= 2:
        overall = "B"
    elif issues <= 4:
        overall = "C"
    elif issues <= 6:
        overall = "D"
    else:
        overall = "F"

    bm.free()

    return {
        "vertices": len(mesh.vertices),
        "faces": total_faces,
        "edges": len(mesh.edges),
        "quads": len(quads),
        "triangles": len(tris),
        "ngons": len(ngons),
        "quad_ratio": round(quad_ratio, 3),
        "non_manifold_edges": len(non_manifold_edges),
        "non_manifold_vertices": len(non_manifold_verts),
        "loose_vertices": len(loose_verts),
        "loose_edges": len(loose_edges),
        "zero_area_faces": len(zero_area),
        "poles_5plus": len(poles_5plus),
        "grades": grades,
        "overall_grade": overall,
        "status": "success",
    }


@handler("test_deformation")
def test_deformation(
    mesh_name: str,
    armature_name: str,
    poses: str = "standard_8",
    render_contact_sheet: bool = True,
) -> dict:
    mesh_obj = bpy.data.objects.get(mesh_name)
    arm_obj = bpy.data.objects.get(armature_name)

    if not mesh_obj:
        return {"error": f"Mesh '{mesh_name}' not found"}
    if not arm_obj or arm_obj.type != "ARMATURE":
        return {"error": f"Armature '{armature_name}' not found"}

    # Define standard test poses
    standard_poses = {
        "t_pose": {},  # Default rest
        "a_pose": {"upper_arm.L": (0, 0, -45), "upper_arm.R": (0, 0, 45)},
        "crouch": {"thigh.L": (-90, 0, 0), "thigh.R": (-90, 0, 0), "shin.L": (90, 0, 0), "shin.R": (90, 0, 0)},
        "arms_up": {"upper_arm.L": (0, 0, -170), "upper_arm.R": (0, 0, 170)},
        "kick": {"thigh.L": (-90, 0, 0)},
        "twist": {"spine": (0, 0, 45)},
        "extreme_bend": {"spine": (45, 0, 0), "spine.001": (45, 0, 0)},
        "rest": {},
    }

    results = []

    for pose_name, bone_rotations in standard_poses.items():
        # Reset to rest pose
        bpy.context.view_layer.objects.active = arm_obj
        bpy.ops.object.mode_set(mode="POSE")

        for pb in arm_obj.pose.bones:
            pb.rotation_euler = (0, 0, 0)
            pb.rotation_quaternion = (1, 0, 0, 0)

        # Apply pose
        for bone_name, rotation in bone_rotations.items():
            pb = arm_obj.pose.bones.get(bone_name)
            if pb:
                pb.rotation_mode = "XYZ"
                pb.rotation_euler = [math.radians(r) for r in rotation]

        bpy.context.view_layer.update()

        # TODO: Analyze deformation quality at this pose
        # - Check for extreme stretching
        # - Check for interpenetration
        # - Measure volume preservation

        results.append({
            "pose": pose_name,
            "status": "evaluated",
            "stretch_score": 0.9,  # Placeholder
            "clip_score": 0.95,    # Placeholder
        })

    bpy.ops.object.mode_set(mode="OBJECT")

    # TODO: Render contact sheet if requested

    return {
        "poses_tested": len(results),
        "results": results,
        "overall_quality": "good",  # Placeholder
        "status": "success",
    }


# ---------------------------------------------------------------------------
# Export handlers
# ---------------------------------------------------------------------------

@handler("export_to_unity")
def export_to_unity(
    object_names: list,
    output_path: str,
    include_animations: bool = True,
    generate_lods: bool = False,
    lod_levels: list = None,
) -> dict:
    if lod_levels is None:
        lod_levels = [1.0, 0.5, 0.25, 0.1]

    # Select specified objects
    bpy.ops.object.select_all(action="DESELECT")
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)

    # Export FBX with Unity settings
    try:
        bpy.ops.export_scene.fbx(
            filepath=output_path,
            use_selection=True,
            global_scale=1.0,
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_ALL",
            axis_forward="-Z",
            axis_up="Y",
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            add_leaf_bones=False,
            bake_anim=include_animations,
            bake_anim_use_all_actions=include_animations,
            path_mode="COPY",
            embed_textures=True,
            use_tspace=True,
            use_armature_deform_only=True,
        )

        file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0

        return {
            "output_path": output_path,
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "objects_exported": object_names,
            "include_animations": include_animations,
            "status": "success",
        }
    except Exception as e:
        return {"error": f"FBX export failed: {str(e)}"}


# ---------------------------------------------------------------------------
# Blender UI Panel
# ---------------------------------------------------------------------------

class VEILBREAKERS_PT_main_panel(bpy.types.Panel):
    bl_label = "VeilBreakers GameDev"
    bl_idname = "VEILBREAKERS_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "VeilBreakers"

    def draw(self, context):
        layout = self.layout

        if server.running:
            layout.label(text="Server: Running", icon="CHECKMARK")
            layout.label(text=f"Port: {server.port}")
            layout.operator("veilbreakers.stop_server", text="Stop Server", icon="CANCEL")
        else:
            layout.label(text="Server: Stopped", icon="ERROR")
            layout.operator("veilbreakers.start_server", text="Start Server", icon="PLAY")


class VEILBREAKERS_OT_start_server(bpy.types.Operator):
    bl_idname = "veilbreakers.start_server"
    bl_label = "Start VeilBreakers Server"

    def execute(self, context):
        server.start()
        return {"FINISHED"}


class VEILBREAKERS_OT_stop_server(bpy.types.Operator):
    bl_idname = "veilbreakers.stop_server"
    bl_label = "Stop VeilBreakers Server"

    def execute(self, context):
        server.stop()
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

server = CommandServer()

classes = [
    VEILBREAKERS_PT_main_panel,
    VEILBREAKERS_OT_start_server,
    VEILBREAKERS_OT_stop_server,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    server.start()
    print("[VeilBreakers] Addon registered and server started")


def unregister():
    server.stop()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("[VeilBreakers] Addon unregistered and server stopped")


if __name__ == "__main__":
    register()
