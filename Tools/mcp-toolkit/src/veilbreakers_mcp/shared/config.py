from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    blender_host: str = "localhost"
    blender_port: int = 9876
    blender_timeout: int = 300

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
