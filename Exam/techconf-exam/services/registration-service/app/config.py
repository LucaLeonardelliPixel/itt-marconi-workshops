"""Centralized registration-service runtime configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    port: int = 5003
    user_service_url: str = "http://localhost:5001"
    event_service_url: str = "http://localhost:5002"
    storage_backend: str = "memory"
    data_dir: Path = Path("./data")
    dependency_timeout: float = 2.0


def load_settings() -> Settings:
    backend = os.environ.get("STORAGE_BACKEND", "memory").strip().lower()
    if backend not in {"memory", "json", "sqlite"}:
        raise ValueError("STORAGE_BACKEND must be memory, json, or sqlite")
    return Settings(
        port=int(os.environ.get("PORT", "5003")),
        user_service_url=os.environ.get(
            "USER_SERVICE_URL", "http://localhost:5001"
        ).rstrip("/"),
        event_service_url=os.environ.get(
            "EVENT_SERVICE_URL", "http://localhost:5002"
        ).rstrip("/"),
        storage_backend=backend,
        data_dir=Path(os.environ.get("DATA_DIR", "./data")),
    )
