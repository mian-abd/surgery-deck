"""Central configuration, driven by environment variables (.env)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Core ---
    db_url: str = "sqlite:///./orguard.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Storage ---
    storage_backend: str = "local"  # local | gcs
    evidence_dir: str = "./evidence"
    gcs_bucket: str = ""

    # --- Perception ---
    surgical_model: str = "doccheck"   # doccheck | ultralytics | none
    person_model: str = "yolo11n.pt"
    models_dir: str = "./models"
    detect_conf: float = 0.35
    detect_every_n: int = 1

    # --- Hygiene rules ---
    hygiene_min_dwell_sec: float = 3.0
    hygiene_window_sec: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
