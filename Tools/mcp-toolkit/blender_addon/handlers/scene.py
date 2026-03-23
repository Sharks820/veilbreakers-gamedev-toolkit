import bpy


def handle_get_scene_info(params: dict) -> dict:
    scene = bpy.context.scene
    objects = []
    for obj in bpy.data.objects:
        objects.append({
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "visible": obj.visible_get(),
        })
    return {
        "name": scene.name,
        "objects": objects,
        "object_count": len(objects),
        "render_engine": scene.render.engine,
        "fps": scene.render.fps,
        "frame_start": scene.frame_start,
        "frame_end": scene.frame_end,
        "unit_scale": scene.unit_settings.scale_length,
    }


def handle_clear_scene(params: dict) -> dict:
    # Use bpy.data API directly — avoids operator context issues from timer
    count = len(bpy.data.objects)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    return {"cleared": True, "objects_removed": count}


def handle_configure_scene(params: dict) -> dict:
    scene = bpy.context.scene
    if params.get("render_engine") is not None:
        scene.render.engine = params["render_engine"]
    if params.get("fps") is not None:
        scene.render.fps = params["fps"]
    if params.get("unit_scale") is not None:
        scene.unit_settings.scale_length = params["unit_scale"]
    return {
        "render_engine": scene.render.engine,
        "fps": scene.render.fps,
        "unit_scale": scene.unit_settings.scale_length,
    }


def handle_list_objects(params: dict) -> list:
    return [
        {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "visible": obj.visible_get(),
        }
        for obj in bpy.data.objects
    ]


# ---------------------------------------------------------------------------
# Collection management (SC-02)
# ---------------------------------------------------------------------------


def handle_create_collection(params: dict) -> dict:
    """Create a new collection and link it to a parent collection.

    Args (via params):
        name: Collection name to create.
        parent: Parent collection name (default "Scene Collection").

    Returns:
        Dict with created collection name and parent.
    """
    name = params.get("name")
    if not name:
        return {"error": "name is required"}

    parent_name = params.get("parent", "Scene Collection")

    # Resolve parent collection
    if parent_name == "Scene Collection":
        parent_col = bpy.context.scene.collection
    else:
        parent_col = bpy.data.collections.get(parent_name)
        if parent_col is None:
            return {"error": f"Parent collection '{parent_name}' not found"}

    # Create collection if it doesn't already exist
    if name in bpy.data.collections:
        col = bpy.data.collections[name]
    else:
        col = bpy.data.collections.new(name)

    # Link to parent if not already linked
    if col.name not in [c.name for c in parent_col.children]:
        parent_col.children.link(col)

    return {
        "collection": col.name,
        "parent": parent_name,
        "created": True,
    }


def handle_organize_by_type(params: dict) -> dict:
    """Auto-organize scene objects into collections by type.

    Categories:
        Characters -- armatures and their children
        Props -- mesh objects with < 5000 polys
        Environment -- mesh objects with >= 5000 polys
        Lights -- light objects
        Cameras -- camera objects
        Empties -- empty objects (markers, sockets)
    """
    categories = {
        "Characters": [],
        "Props": [],
        "Environment": [],
        "Lights": [],
        "Cameras": [],
        "Empties": [],
    }

    scene_col = bpy.context.scene.collection

    # Build set of armature child objects (these go under Characters)
    armature_children = set()
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            for child in obj.children_recursive:
                armature_children.add(child.name)

    # Classify each object
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE' or obj.name in armature_children:
            categories["Characters"].append(obj)
        elif obj.type == 'MESH':
            poly_count = len(obj.data.polygons) if obj.data else 0
            if poly_count < 5000:
                categories["Props"].append(obj)
            else:
                categories["Environment"].append(obj)
        elif obj.type == 'LIGHT':
            categories["Lights"].append(obj)
        elif obj.type == 'CAMERA':
            categories["Cameras"].append(obj)
        elif obj.type == 'EMPTY':
            categories["Empties"].append(obj)

    moved_counts = {}

    for cat_name, objects in categories.items():
        if not objects:
            continue

        # Create collection if it doesn't exist
        if cat_name in bpy.data.collections:
            col = bpy.data.collections[cat_name]
        else:
            col = bpy.data.collections.new(cat_name)

        # Link to scene collection if not already linked
        if col.name not in [c.name for c in scene_col.children]:
            scene_col.children.link(col)

        count = 0
        for obj in objects:
            # Unlink from all current collections
            for old_col in list(obj.users_collection):
                old_col.objects.unlink(obj)
            # Link to new collection
            col.objects.link(obj)
            count += 1

        moved_counts[cat_name] = count

    return {
        "organized": True,
        "moved": moved_counts,
        "total_objects": sum(moved_counts.values()),
    }


def handle_toggle_collection_visibility(params: dict) -> dict:
    """Toggle collection visibility in viewport and render.

    Args (via params):
        collection_name: Which collection to toggle.
        visible: Bool -- whether the collection should be visible.

    Returns:
        Dict with collection name and new visibility state.
    """
    collection_name = params.get("collection_name")
    if not collection_name:
        return {"error": "collection_name is required"}

    visible = params.get("visible", True)

    col = bpy.data.collections.get(collection_name)
    if col is None:
        return {"error": f"Collection '{collection_name}' not found"}

    # Set hide_viewport and hide_render (inverted from visible)
    col.hide_viewport = not visible
    col.hide_render = not visible

    # Also update the view layer's layer collection exclude state
    def _set_layer_collection(layer_col, target_name, exclude):
        if layer_col.name == target_name:
            layer_col.exclude = exclude
            return True
        for child in layer_col.children:
            if _set_layer_collection(child, target_name, exclude):
                return True
        return False

    view_layer = bpy.context.view_layer
    _set_layer_collection(view_layer.layer_collection, collection_name, not visible)

    return {
        "collection": collection_name,
        "visible": visible,
    }


def handle_list_collections(params: dict) -> dict:
    """Return a tree of all collections with object counts.

    Returns:
        Dict with collection tree structure.
    """
    def _build_tree(collection):
        children = []
        for child in collection.children:
            children.append(_build_tree(child))
        return {
            "name": collection.name,
            "object_count": len(collection.objects),
            "children": children,
            "hide_viewport": getattr(collection, "hide_viewport", False),
            "hide_render": getattr(collection, "hide_render", False),
        }

    scene_col = bpy.context.scene.collection
    tree = {
        "name": scene_col.name,
        "object_count": len(scene_col.objects),
        "children": [_build_tree(child) for child in scene_col.children],
    }

    return {"collections": tree}
