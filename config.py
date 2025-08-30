# backend/config.py
from __future__ import annotations
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ASSEMBLYAI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    MURF_API_KEY: str | None = None

    class Config:
        env_file = ".env"

settings = Settings()
