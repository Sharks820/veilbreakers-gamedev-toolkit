from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    blender_host: str = "localhost"
    blender_port: int = 9876
    blender_timeout: int = 300

    # Tripo3D AI 3D generation
    tripo_api_key: str = ""
    # fal.ai for concept art / image generation
    fal_key: str = ""
    # Real-ESRGAN binary path for texture upscaling
    realesrgan_path: str = "bin/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe"
    # SQLite asset catalog database path
    asset_catalog_db: str = "assets.db"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
