import json
import os
from dataclasses import dataclass, field
from typing import Any


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    discord_token: str = os.getenv("DISCORD_TOKEN", "")
    channel_id: int = int(os.getenv("CHANNEL_ID", "0"))
    send_startup_message: bool = _bool("SEND_STARTUP_MESSAGE", True)
    scan_on_startup: bool = _bool("SCAN_ON_STARTUP", True)
    poll_minutes: int = int(os.getenv("POLL_MINUTES", "20"))
    state_file: str = os.getenv("STATE_FILE", "state.json")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    max_source_text_chars: int = int(os.getenv("MAX_SOURCE_TEXT_CHARS", "4000"))
    max_sources_per_cycle: int = int(os.getenv("MAX_SOURCES_PER_CYCLE", "12"))
    newswire_rss_url: str = os.getenv(
        "NEWSWIRE_RSS_URL",
        "https://www.rockstargames.com/newswire/rss",
    )
    sources: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Settings":
        instance = cls()
        raw_sources = os.getenv("SOURCES_JSON", "[]")
        try:
            parsed = json.loads(raw_sources)
            if isinstance(parsed, list):
                instance.sources = parsed
            else:
                raise ValueError("SOURCES_JSON must be a JSON array")
        except Exception as exc:
            raise RuntimeError(f"Invalid SOURCES_JSON: {exc}") from exc
        return instance
