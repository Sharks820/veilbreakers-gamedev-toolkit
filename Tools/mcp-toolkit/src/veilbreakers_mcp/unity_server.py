"""VeilBreakers Unity MCP Server.

FastMCP server providing Unity Editor automation tools. Generates C# editor
scripts that are written to the Unity project and compiled/executed via the
VB toolkit's own TCP bridge (UnityConnection on port 9877).

Entry point: vb-unity-mcp (see pyproject.toml [project.scripts])

This module serves as the entry point -- all tool handlers live in
the ``unity_tools`` subpackage.
"""

# Import the shared mcp instance with all tools registered via side-effect imports
from veilbreakers_mcp.unity_tools import mcp  # noqa: F401


def main():
    """Entry point for the vb-unity-mcp server."""
    mcp.run()


if __name__ == "__main__":
    main()
