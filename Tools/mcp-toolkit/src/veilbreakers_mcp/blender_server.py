from mcp.server.fastmcp import FastMCP
from veilbreakers_mcp.shared.blender_client import BlenderConnection
from veilbreakers_mcp.shared.config import Settings

settings = Settings()
mcp = FastMCP(
    "veilbreakers-blender",
    instructions="VeilBreakers Blender game development tools",
)

_connection: BlenderConnection | None = None


def get_blender_connection() -> BlenderConnection:
    global _connection
    if _connection is None or not _connection.is_alive():
        _connection = BlenderConnection(
            host=settings.blender_host,
            port=settings.blender_port,
            timeout=settings.blender_timeout,
        )
        _connection.connect()
    return _connection


@mcp.tool()
async def blender_ping() -> str:
    """Check if Blender is connected and responsive."""
    blender = get_blender_connection()
    result = await blender.send_command("ping")
    return f"Blender connection OK: {result}"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
