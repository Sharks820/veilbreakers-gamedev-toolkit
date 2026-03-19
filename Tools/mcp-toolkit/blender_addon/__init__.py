bl_info = {
    "name": "VeilBreakers MCP Bridge",
    "author": "VeilBreakers",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > VeilBreakers",
    "description": "MCP bridge for AI-driven game development",
    "category": "Development",
}

import bpy

_server = None
_auto_start_timer = None


def _deferred_auto_start():
    """One-shot timer: auto-start the MCP server after addon loads."""
    global _server
    try:
        from .socket_server import BlenderMCPServer
        _server = BlenderMCPServer()
        _server.start()
        print("[VeilBreakers MCP] Server auto-started on port 9876")
    except Exception as e:
        print(f"[VeilBreakers MCP] Auto-start failed: {e}")
    return None  # Do not reschedule


class VEILBREAKERS_OT_start_mcp_server(bpy.types.Operator):
    bl_idname = "veilbreakers.start_mcp_server"
    bl_label = "Start MCP Server"
    bl_description = "Start the VeilBreakers MCP bridge server"

    def execute(self, context):
        global _server
        if _server is not None and _server.running:
            self.report({"WARNING"}, "Server already running")
            return {"CANCELLED"}
        from .socket_server import BlenderMCPServer
        _server = BlenderMCPServer()
        _server.start()
        self.report({"INFO"}, f"MCP server started on port {_server.port}")
        return {"FINISHED"}


class VEILBREAKERS_OT_stop_mcp_server(bpy.types.Operator):
    bl_idname = "veilbreakers.stop_mcp_server"
    bl_label = "Stop MCP Server"
    bl_description = "Stop the VeilBreakers MCP bridge server"

    def execute(self, context):
        global _server
        if _server is None or not _server.running:
            self.report({"WARNING"}, "Server not running")
            return {"CANCELLED"}
        _server.stop()
        _server = None
        self.report({"INFO"}, "MCP server stopped")
        return {"FINISHED"}


class VEILBREAKERS_PT_mcp_panel(bpy.types.Panel):
    bl_label = "VeilBreakers MCP"
    bl_idname = "VEILBREAKERS_PT_mcp_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "VeilBreakers"

    def draw(self, context):
        layout = self.layout
        global _server
        if _server is not None and _server.running:
            layout.label(text="Status: Running", icon="PLAY")
            layout.label(text=f"Port: {_server.port}")
            layout.operator("veilbreakers.stop_mcp_server", icon="PAUSE")
        else:
            layout.label(text="Status: Stopped", icon="SNAP_FACE")
            layout.operator("veilbreakers.start_mcp_server", icon="PLAY")


_classes = (
    VEILBREAKERS_OT_start_mcp_server,
    VEILBREAKERS_OT_stop_mcp_server,
    VEILBREAKERS_PT_mcp_panel,
)


def register():
    global _auto_start_timer
    for cls in _classes:
        bpy.utils.register_class(cls)
    _auto_start_timer = _deferred_auto_start
    bpy.app.timers.register(_auto_start_timer, first_interval=1.0)


def unregister():
    global _server, _auto_start_timer
    if _auto_start_timer is not None and bpy.app.timers.is_registered(_auto_start_timer):
        bpy.app.timers.unregister(_auto_start_timer)
        _auto_start_timer = None
    if _server is not None:
        _server.stop()
        _server = None
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
