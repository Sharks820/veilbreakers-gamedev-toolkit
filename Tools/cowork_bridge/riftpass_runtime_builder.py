"""Runtime builder executed inside Blender for Riftpass_01 hero features."""

import json
import math

import bmesh
import bpy
from mathutils import Vector


def _ensure_collection(name: str) -> bpy.types.Collection:
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def _link_object(obj: bpy.types.Object, coll: bpy.types.Collection) -> None:
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    for existing in list(obj.users_collection):
        if existing != coll:
            existing.objects.unlink(obj)


def _set_active(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _apply_all_modifiers(obj: bpy.types.Object) -> None:
    _set_active(obj)
    for mod in list(obj.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception:
            pass


def _apply_transforms(obj: bpy.types.Object) -> None:
    _set_active(obj)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)


def _origin_to_geometry(obj: bpy.types.Object) -> None:
    _set_active(obj)
    try:
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
    except Exception:
        pass


def _smart_uv(obj: bpy.types.Object) -> None:
    _set_active(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")


def _shade_smooth(obj: bpy.types.Object) -> None:
    if obj.type != "MESH" or obj.data is None:
        return
    for poly in obj.data.polygons:
        poly.use_smooth = True
    if hasattr(obj.data, "use_auto_smooth"):
        obj.data.use_auto_smooth = True
    if hasattr(obj.data, "auto_smooth_angle"):
        obj.data.auto_smooth_angle = math.radians(42.0)


def _shade_flat(obj: bpy.types.Object) -> None:
    if obj.type != "MESH" or obj.data is None:
        return
    for poly in obj.data.polygons:
        poly.use_smooth = False


def _ensure_principled_material(
    name: str,
    *,
    base_color: tuple[float, float, float, float],
    roughness: float,
    metallic: float = 0.0,
    transmission: float = 0.0,
    alpha: float = 1.0,
    emission_color: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (480, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (180, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Alpha"].default_value = alpha
    bsdf.inputs["Transmission Weight"].default_value = transmission
    bsdf.inputs["IOR"].default_value = 1.333 if transmission > 0.0 else 1.45
    if emission_color is not None:
        bsdf.inputs["Emission Color"].default_value = emission_color
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    mat.blend_method = "HASHED" if alpha < 1.0 or transmission > 0.0 else "OPAQUE"
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "HASHED"
    return mat


def _assign_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.type != "MESH" or obj.data is None:
        return
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def _cleanup_existing(prefixes: list[str]) -> None:
    targets: list[bpy.types.Object] = []
    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(prefix) for prefix in prefixes):
            targets.append(obj)
    for obj in targets:
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None:
            try:
                if obj.type == "MESH":
                    bpy.data.meshes.remove(data)
                elif obj.type == "META":
                    bpy.data.metaballs.remove(data)
                elif obj.type == "CURVE":
                    bpy.data.curves.remove(data)
            except Exception:
                pass


def _roughen_mesh(
    obj: bpy.types.Object,
    *,
    strength: float,
    scale_a: float,
    scale_b: float,
    directional_bias: float = 1.0,
) -> None:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.normal_update()
    for vert in bm.verts:
        pos = vert.co.copy()
        nrm = vert.normal.normalized() if vert.normal.length > 1e-6 else Vector((0.0, 0.0, 1.0))
        base = (
            math.sin(pos.x * scale_a + pos.z * 0.21)
            + 0.7 * math.cos(pos.y * scale_b - pos.z * 0.17)
            + 0.5 * math.sin((pos.x + pos.y) * 0.16)
        )
        shard = (
            0.65 * math.sin(pos.x * 0.52 - pos.y * 0.31 + pos.z * 0.09)
            + 0.4 * math.cos(pos.x * 0.38 + pos.y * 0.44)
        )
        ledge = math.floor((pos.z + 24.0) * 0.22) * 0.18
        mask = max(0.0, min(1.0, (pos.z + 10.0) / 45.0))
        side_mask = 0.55 + 0.45 * max(0.0, min(1.0, (pos.x + directional_bias * 12.0) / 48.0))
        tangent = Vector((nrm.y, -nrm.x, 0.0))
        if tangent.length > 1e-6:
            tangent.normalize()
        vert.co += nrm * ((base + ledge) * strength * mask * side_mask)
        vert.co += tangent * (shard * strength * 0.12 * mask)
    bm.to_mesh(obj.data)
    obj.data.update()
    bm.free()


def _make_metaball_mesh(
    name: str,
    parts: list[dict],
    collection: bpy.types.Collection,
    *,
    resolution: float,
    render_resolution: float,
) -> bpy.types.Object:
    mb = bpy.data.metaballs.new(f"{name}_Meta")
    mb.resolution = resolution
    mb.render_resolution = render_resolution
    obj = bpy.data.objects.new(name, mb)
    _link_object(obj, collection)
    for index, part in enumerate(parts):
        elem = mb.elements.new(type="BALL")
        elem.co = Vector(part["co"])
        elem.radius = float(part["radius"])
        elem.stiffness = float(part.get("stiffness", 2.0))
        if index == 0:
            elem.use_negative = bool(part.get("negative", False))
    _set_active(obj)
    bpy.ops.object.convert(target="MESH")
    converted = bpy.context.view_layer.objects.active
    converted.name = name
    _link_object(converted, collection)
    return converted


def _cluster_hull_mesh(
    name: str,
    parts: list[dict],
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    _link_object(obj, collection)

    bm = bmesh.new()
    seed_dirs = [
        Vector((1.0, 0.0, 0.18)),
        Vector((-1.0, 0.0, 0.12)),
        Vector((0.0, 1.0, 0.28)),
        Vector((0.0, -1.0, -0.18)),
        Vector((0.66, 0.72, 0.82)),
        Vector((-0.58, 0.78, 0.64)),
        Vector((0.62, -0.68, 0.54)),
        Vector((-0.74, -0.52, 0.36)),
        Vector((0.16, 0.14, 1.08)),
        Vector((-0.18, -0.22, -0.72)),
    ]
    for idx, part in enumerate(parts):
        center = Vector(part["co"])
        radius = float(part["radius"])
        twist = 0.2 * math.sin(idx * 1.37)
        for dir_idx, base_dir in enumerate(seed_dirs):
            direction = base_dir.normalized()
            skew = Vector((
                0.12 * math.sin(idx + dir_idx * 0.7),
                0.09 * math.cos(idx * 0.5 + dir_idx * 0.4),
                0.11 * math.sin(idx * 0.3 + dir_idx),
            ))
            scale = Vector((
                radius * (0.82 + 0.12 * math.sin(dir_idx + twist)),
                radius * (0.74 + 0.16 * math.cos(dir_idx * 0.6)),
                radius * (0.34 + 0.16 * max(0.0, direction.z)),
            ))
            point = center + Vector((
                (direction.x + skew.x) * scale.x,
                (direction.y + skew.y) * scale.y,
                (direction.z + skew.z) * scale.z,
            ))
            bm.verts.new(point)
    bm.verts.ensure_lookup_table()
    bmesh.ops.convex_hull(bm, input=list(bm.verts))
    bm.to_mesh(mesh)
    mesh.update()
    bm.free()
    return obj


def _tube_mesh(
    name: str,
    parts: list[dict],
    collection: bpy.types.Collection,
    *,
    sides: int,
    vertical_scale: float = 1.0,
    lateral_scale: float = 1.0,
    cap_ends: bool = True,
) -> bpy.types.Object:
    vectors = [Vector(part["co"]) for part in parts]
    radii = [float(part["radius"]) for part in parts]
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for idx, point in enumerate(vectors):
        if idx == 0:
            tangent = (vectors[idx + 1] - point).normalized()
        elif idx == len(vectors) - 1:
            tangent = (point - vectors[idx - 1]).normalized()
        else:
            tangent = (vectors[idx + 1] - vectors[idx - 1]).normalized()
        up = Vector((0.0, 0.0, 1.0))
        side = tangent.cross(up)
        if side.length < 1e-6:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        normal = side.cross(tangent).normalized()
        radius = radii[idx]
        for side_idx in range(sides):
            ang = (side_idx / sides) * math.tau
            profile = 1.0 + 0.16 * math.sin(side_idx * 1.9 + idx * 0.6) + 0.08 * math.cos(side_idx * 2.7 - idx * 0.3)
            ring_x = math.cos(ang) * radius * lateral_scale * profile
            ring_z = math.sin(ang) * radius * vertical_scale * profile
            if math.sin(ang) < 0.0:
                ring_z *= 0.52
            else:
                ring_z *= 1.14
            side_warp = 0.14 * radius * math.sin(idx * 0.7 + side_idx * 0.9)
            roof_warp = 0.10 * radius * math.cos(idx * 0.5 - side_idx * 0.6)
            pos = point + side * (ring_x + side_warp) + normal * (ring_z + roof_warp)
            verts.append(tuple(pos))

    for idx in range(len(vectors) - 1):
        base = idx * sides
        next_base = (idx + 1) * sides
        for side_idx in range(sides):
            a = base + side_idx
            b = base + ((side_idx + 1) % sides)
            c = next_base + ((side_idx + 1) % sides)
            d = next_base + side_idx
            faces.append((a, b, c, d))

    if cap_ends:
        start_center = len(verts)
        verts.append(tuple(vectors[0]))
        end_center = len(verts)
        verts.append(tuple(vectors[-1]))
        for side_idx in range(sides):
            nxt = (side_idx + 1) % sides
            faces.append((start_center, nxt, side_idx))
            faces.append((end_center, (len(vectors) - 1) * sides + side_idx, (len(vectors) - 1) * sides + nxt))

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link_object(obj, collection)
    return obj


def _strip_mesh(
    name: str,
    points: list[list[float]],
    widths: list[float],
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []
    vectors = [Vector(pt) for pt in points]
    for idx, point in enumerate(vectors):
        if idx == 0:
            tangent = (vectors[idx + 1] - point).normalized()
        elif idx == len(vectors) - 1:
            tangent = (point - vectors[idx - 1]).normalized()
        else:
            tangent = (vectors[idx + 1] - vectors[idx - 1]).normalized()
        side = Vector((-tangent.y, tangent.x, 0.0))
        if side.length < 1e-6:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        half_width = widths[idx] * 0.5
        left = point + side * half_width
        right = point - side * half_width
        verts.extend([tuple(left), tuple(right)])
        if idx > 0:
            base = idx * 2
            faces.append((base - 2, base - 1, base + 1, base))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link_object(obj, collection)
    return obj


def _ellipse_pool(
    name: str,
    center: list[float],
    radius_x: float,
    radius_y: float,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    segments = 28
    verts = [tuple(center)]
    faces = []
    for i in range(segments):
        angle = (i / segments) * math.tau
        verts.append((
            center[0] + math.cos(angle) * radius_x,
            center[1] + math.sin(angle) * radius_y,
            center[2],
        ))
    for i in range(1, segments + 1):
        j = 1 if i == segments else i + 1
        faces.append((0, i, j))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    _link_object(obj, collection)
    return obj


def _join_objects(name: str, objects: list[bpy.types.Object], collection: bpy.types.Collection) -> bpy.types.Object:
    _set_active(objects[0])
    for obj in objects[1:]:
        obj.select_set(True)
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    _link_object(joined, collection)
    return joined


def build_from_spec(spec: dict) -> dict:
    _cleanup_existing([
        "Riftpass_01_CliffMass",
        "Riftpass_01_Cave",
        "Riftpass_01_Waterfall",
        "Riftpass_01_RiverWater",
        "Riftpass_01_BasinWater",
        "Riftpass_01_HeroRock",
        "Riftpass_01_Mist",
    ])
    hero_coll = _ensure_collection("Riftpass_01_Hero")
    node = bpy.data.objects.get("Riftpass_01_Node")
    terrain_obj = bpy.data.objects.get("Riftpass_01_Terrain")
    if terrain_obj is None:
        raise RuntimeError("Riftpass_01_Terrain not found")

    rock_mat = _ensure_principled_material(
        "Riftpass_01_Rock_Mat",
        base_color=(0.31, 0.27, 0.23, 1.0),
        roughness=0.82,
    )
    cave_mat = _ensure_principled_material(
        "Riftpass_01_Cave_Mat",
        base_color=(0.25, 0.20, 0.17, 1.0),
        roughness=0.9,
    )
    water_mat = _ensure_principled_material(
        "Riftpass_01_Water_Mat",
        base_color=(0.18, 0.40, 0.44, 0.98),
        roughness=0.06,
        transmission=0.68,
        alpha=0.97,
        emission_color=(0.14, 0.42, 0.46, 1.0),
        emission_strength=0.62,
    )
    mist_mat = _ensure_principled_material(
        "Riftpass_01_Mist_Mat",
        base_color=(0.82, 0.88, 0.92, 0.28),
        roughness=0.28,
        alpha=0.28,
        transmission=0.1,
        emission_color=(0.28, 0.38, 0.42, 1.0),
        emission_strength=0.22,
    )

    cliff_obj = _cluster_hull_mesh(
        "Riftpass_01_CliffMass",
        spec["cliff_parts"][:4],
        hero_coll,
    )
    remesh = cliff_obj.modifiers.new("RiftpassVoxel", "REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = 0.7
    remesh.adaptivity = 0.0
    _apply_all_modifiers(cliff_obj)
    _roughen_mesh(cliff_obj, strength=0.35, scale_a=0.23, scale_b=0.19, directional_bias=1.0)
    _assign_material(cliff_obj, rock_mat)
    _shade_smooth(cliff_obj)

    cave_cutter = _tube_mesh(
        "Riftpass_01_CaveCutter",
        spec["cave_parts"],
        hero_coll,
        sides=14,
        vertical_scale=0.95,
        lateral_scale=1.08,
        cap_ends=True,
    )
    route_preview = cave_cutter.copy()
    route_preview.data = cave_cutter.data.copy()
    route_preview.name = "Riftpass_01_CaveRoute"
    _link_object(route_preview, hero_coll)
    _assign_material(route_preview, cave_mat)
    route_remesh = route_preview.modifiers.new("RouteVoxel", "REMESH")
    route_remesh.mode = "VOXEL"
    route_remesh.voxel_size = 0.8
    _apply_all_modifiers(route_preview)
    _roughen_mesh(route_preview, strength=0.25, scale_a=0.31, scale_b=0.27, directional_bias=0.0)
    _shade_smooth(route_preview)

    bool_mod = terrain_obj.modifiers.new("CaveCarve", "BOOLEAN")
    bool_mod.operation = "DIFFERENCE"
    bool_mod.solver = "EXACT"
    bool_mod.object = cave_cutter
    _apply_all_modifiers(terrain_obj)
    cave_cutter.hide_set(True)
    cave_cutter.hide_render = True

    waterfall_points = [part["co"] for part in spec["waterfall_parts"]]
    waterfall_widths = [max(1.4, float(part["radius"]) * 1.45) for part in spec["waterfall_parts"]]
    waterfall_obj = _strip_mesh(
        "Riftpass_01_Waterfall",
        waterfall_points,
        waterfall_widths,
        hero_coll,
    )
    wf_solidify = waterfall_obj.modifiers.new("WaterSolidify", "SOLIDIFY")
    wf_solidify.thickness = 0.18
    wf_solidify.offset = 0.0
    wf_subd = waterfall_obj.modifiers.new("WaterSubd", "SUBSURF")
    wf_subd.levels = 1
    wf_subd.render_levels = 1
    _apply_all_modifiers(waterfall_obj)
    _assign_material(waterfall_obj, water_mat)
    _shade_smooth(waterfall_obj)

    river_obj = _strip_mesh(
        "Riftpass_01_RiverWater",
        spec["river_surface_points"],
        spec["river_widths"],
        hero_coll,
    )
    basin_obj = _ellipse_pool(
        "Riftpass_01_BasinWater",
        spec["pool_center"],
        spec["pool_radius_x"],
        spec["pool_radius_y"],
        hero_coll,
    )
    river_joined = _join_objects("Riftpass_01_RiverWater", [river_obj, basin_obj], hero_coll)
    solidify = river_joined.modifiers.new("WaterSolidify", "SOLIDIFY")
    solidify.thickness = 0.14
    solidify.offset = 0.0
    subd = river_joined.modifiers.new("WaterSubd", "SUBSURF")
    subd.levels = 2
    subd.render_levels = 2
    _apply_all_modifiers(river_joined)
    _assign_material(river_joined, water_mat)
    _shade_smooth(river_joined)

    mist_parts = [
        {"co": spec["mist_center"], "radius": 6.5},
        {"co": [spec["mist_center"][0] + 2.5, spec["mist_center"][1] - 2.0, spec["mist_center"][2] + 1.8], "radius": 4.8},
        {"co": [spec["mist_center"][0] - 3.0, spec["mist_center"][1] + 2.5, spec["mist_center"][2] + 1.0], "radius": 5.3},
    ]
    mist_obj = _make_metaball_mesh(
        "Riftpass_01_Mist",
        mist_parts,
        hero_coll,
        resolution=0.8,
        render_resolution=0.3,
    )
    _assign_material(mist_obj, mist_mat)
    _shade_smooth(mist_obj)

    hero_rocks: list[bpy.types.Object] = []
    for idx, rock_spec in enumerate(spec["hero_rocks"]):
        rock = _cluster_hull_mesh(
            f"Riftpass_01_HeroRock_{idx+1:02d}",
            rock_spec["parts"],
            hero_coll,
        )
        rock_remesh = rock.modifiers.new("RockVoxel", "REMESH")
        rock_remesh.mode = "VOXEL"
        rock_remesh.voxel_size = 0.65
        _apply_all_modifiers(rock)
        _roughen_mesh(rock, strength=0.32, scale_a=0.35, scale_b=0.26, directional_bias=0.0)
        _assign_material(rock, rock_mat)
        _shade_flat(rock)
        hero_rocks.append(rock)

    for obj in [cliff_obj, route_preview, waterfall_obj, river_joined, mist_obj, *hero_rocks]:
        if node is not None:
            obj.parent = node
        _origin_to_geometry(obj)
        _smart_uv(obj)
        _apply_transforms(obj)

    cliff_obj.hide_render = True
    route_preview.hide_render = True

    return {
        "cliff": cliff_obj.name,
        "cave_route": route_preview.name,
        "waterfall": waterfall_obj.name,
        "river": river_joined.name,
        "mist": mist_obj.name,
        "hero_rocks": [obj.name for obj in hero_rocks],
    }


def build(spec_path: str) -> dict:
    raise RuntimeError("build(spec_path) is disabled in sandboxed execute_code; use build_from_spec(spec)")
