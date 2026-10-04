"""Runtime configuration, loaded from the environment (optionally a .env file)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

try:  # python-dotenv is optional at runtime
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is a convenience only
    pass


def _get(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


class Settings:
    def __init__(self) -> None:
        # Local open-weight inference
        self.llm_base_url = _get("LLM_BASE_URL")
        self.llm_model = _get("LLM_MODEL")
        self.llm_temperature = float(_get("LLM_TEMPERATURE", "0.6") or "0.6")
        self.llm_timeout = float(_get("LLM_TIMEOUT", "120") or "120")

        # Offline-friendly storage: everything stays on this machine
        data_dir = _get("DATA_DIR", "./data")
        self.data_dir = Path(data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "linguapal.db"

        # Optional partner tech
        self.elevenlabs_api_key = _get("ELEVENLABS_API_KEY")
        self.elevenlabs_voice_id = _get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
        self.sentry_dsn = _get("SENTRY_DSN")

        # Server
        self.port = int(_get("PORT", "8000") or "8000")


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
