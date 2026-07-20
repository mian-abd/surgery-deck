"""Central configuration, driven by environment variables (.env)."""
from __future__ import annotations

import json
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
    surgical_model: str = "doccheck"   # none | coco | doccheck | ultralytics
    person_model: str = "yolo11n.pt"
    models_dir: str = "./models"
    detect_conf: float = 0.35
    detect_every_n: int = 1

    # Confidence threshold applied specifically to the surgical-instrument model
    # (the DocCheck YOLOv5 checkpoint tends to want a slightly higher floor).
    instrument_conf: float = 0.35

    # DocCheck (Hugging Face) surgical-instrument weights, used for the
    # "doccheck" path. Downloaded on demand via huggingface_hub.
    hf_model_repo: str = "DocCheck/medical-instrument-detection"
    hf_model_file: str = "instrument_detector_model.pt"

    # Optional JSON object mapping raw model class names -> coarse demo labels,
    # e.g. '{"Chirurgische Schere spitz/spitz": "scissors"}'. Empty string means
    # "use the built-in German->English map in detector.py".
    class_map: str = ""

    # --- Hygiene rules ---
    hygiene_min_dwell_sec: float = 3.0
    hygiene_window_sec: int = 300

    # --- Gemini ---
    # Set GEMINI_API_KEY in .env (never commit it). When unset, every Gemini
    # feature degrades to the rule-based text and nothing raises.
    gemini_api_key: str = ""
    # gemini-2.5-flash is gated for new API keys ("no longer available to new
    # users"), so default to the current flash model. `gemini-flash-latest` also
    # works if you'd rather auto-track the newest release.
    gemini_model: str = "gemini-3.5-flash"
    gemini_enabled: bool = True
    gemini_timeout_sec: float = 20.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def class_map_override(self) -> dict[str, str]:
        """Parse the JSON ``class_map`` env override into a dict.

        Returns an empty dict when unset or malformed (callers then fall back
        to the built-in map baked into the detector).
        """
        raw = (self.class_map or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): str(v) for k, v in data.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
