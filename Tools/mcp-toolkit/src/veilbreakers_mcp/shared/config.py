import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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
    # Stable Fast 3D output texture size in pixels
    stable_fast3d_texture_resolution: int = 1024
    # Stable Fast 3D remesh option: none, triangle, or quad
    stable_fast3d_remesh_option: str = "quad"
    # fal.ai for concept art / image generation
    fal_key: str = ""
    # Real-ESRGAN binary path for texture upscaling
    realesrgan_path: str = "bin/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe"
    # SQLite asset catalog database path
    asset_catalog_db: str = "assets.db"

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
