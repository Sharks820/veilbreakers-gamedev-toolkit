import logging
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# MISC-006: Relative path defaults break when the process CWD is not the
# project root (e.g. OneDrive sync processes, pytest, system services).
# Resolve to absolute paths relative to this config file's own directory.
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
_DEFAULT_DB_PATH = os.path.join(_PROJECT_ROOT, "assets.db")
_DEFAULT_REALESRGAN = os.path.join(
    _PROJECT_ROOT, "bin", "realesrgan-ncnn-vulkan", "realesrgan-ncnn-vulkan.exe"
)


class Settings(BaseSettings):
    blender_host: str = "localhost"
    blender_port: int = 9876
    blender_timeout: int = 300

    # Tripo3D AI 3D generation
    tripo_api_key: str = ""
    # Tripo Studio session token (JWT, expires in 2h)
    tripo_studio_token: str = ""
    # Tripo Studio session cookie (ory_kratos_session, auto-refreshes JWTs, lasts ~25 days)
    tripo_session_cookie: str = ""
    # Preferred local 3D backend for image-to-mesh generation
    preferred_3d_backend: str = "stable_fast_3d"
    # Stable Fast 3D repo clone path (official repo checkout)
    stable_fast3d_repo_path: str = ""
    # Python executable to use for Stable Fast 3D (defaults to current interpreter when empty)
    stable_fast3d_python: str = ""
    # Stable Fast 3D device: auto, cuda, or cpu
    stable_fast3d_device: str = "auto"
    # Stable Fast 3D output texture size in pixels
    stable_fast3d_texture_resolution: int = 512
    # Stable Fast 3D remesh option: none, triangle, or quad
    stable_fast3d_remesh_option: str = "triangle"
    # Stable Fast 3D target vertex count hint
    stable_fast3d_target_vertex_count: int = 20000
    # fal.ai for concept art / image generation
    fal_key: str = ""
    # Real-ESRGAN binary path for texture upscaling
    realesrgan_path: str = _DEFAULT_REALESRGAN
    # SQLite asset catalog database path
    asset_catalog_db: str = _DEFAULT_DB_PATH

    # Unity project root path (for C# script generation)
    unity_project_path: str = ""

    # Unity Editor TCP bridge (direct communication, port 9877)
    unity_bridge_host: str = "localhost"
    unity_bridge_port: int = 9877
    unity_bridge_timeout: int = 300

    # Google Gemini API key for visual review
    gemini_api_key: str = ""
    # ElevenLabs API key for AI audio generation
    elevenlabs_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "pipeline.local.env"),
        env_file_encoding="utf-8",
    )
