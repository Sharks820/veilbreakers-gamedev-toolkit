"""Unity tool modules -- split from unity_server.py monolith.

Each module registers its tool(s) with the shared FastMCP instance
from _common.py. Import all modules to register all tools.
"""

from veilbreakers_mcp.unity_tools._common import (
    mcp,
    settings as _settings_obj,
    logger,
    _strip_registered_tool_titles,
)

from veilbreakers_mcp.unity_tools import editor  # noqa: F401
from veilbreakers_mcp.unity_tools import vfx  # noqa: F401
from veilbreakers_mcp.unity_tools import audio  # noqa: F401
from veilbreakers_mcp.unity_tools import ui  # noqa: F401
from veilbreakers_mcp.unity_tools import scene  # noqa: F401
from veilbreakers_mcp.unity_tools import gameplay  # noqa: F401
from veilbreakers_mcp.unity_tools import performance  # noqa: F401
import veilbreakers_mcp.unity_tools.settings  # noqa: F401
from veilbreakers_mcp.unity_tools import prefab  # noqa: F401
from veilbreakers_mcp.unity_tools import assets  # noqa: F401
from veilbreakers_mcp.unity_tools import code  # noqa: F401
from veilbreakers_mcp.unity_tools import shader  # noqa: F401
from veilbreakers_mcp.unity_tools import data  # noqa: F401
from veilbreakers_mcp.unity_tools import quality  # noqa: F401
from veilbreakers_mcp.unity_tools import pipeline  # noqa: F401
from veilbreakers_mcp.unity_tools import game  # noqa: F401
from veilbreakers_mcp.unity_tools import content  # noqa: F401
from veilbreakers_mcp.unity_tools import camera  # noqa: F401
from veilbreakers_mcp.unity_tools import world  # noqa: F401
from veilbreakers_mcp.unity_tools import ux  # noqa: F401
from veilbreakers_mcp.unity_tools import qa  # noqa: F401
from veilbreakers_mcp.unity_tools import build  # noqa: F401

_strip_registered_tool_titles(mcp)

settings = _settings_obj  # re-export the Settings object (not the module)
__all__ = ["mcp", "settings", "logger"]
