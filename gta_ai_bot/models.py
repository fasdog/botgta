from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

CATEGORY_ORDER = ["weekly", "gunvan", "dealers", "stash", "shipwreck", "caches", "news"]

DEFAULT_STATE: dict[str, dict[str, Any]] = {
    key: {
        "text": "Нет данных.",
        "updated_at": "",
        "hash": "",
        "items": [],
        "sources": [],
    }
    for key in CATEGORY_ORDER
}

META = {
    "gunvan": {"title": "🚚 Gun Van", "color": 0xF59E0B},
    "dealers": {"title": "💊 Street Dealers", "color": 0x22C55E},
    "stash": {"title": "🏠 Stash House", "color": 0x3B82F6},
    "shipwreck": {"title": "🚢 Shipwreck", "color": 0x14B8A6},
    "caches": {"title": "🌊 Hidden Caches", "color": 0xA855F7},
    "news": {"title": "📰 GTA Online News", "color": 0x5865F2},
    "weekly": {"title": "🎯 Weekly Bonuses", "color": 0xEF4444},
}


@dataclass(slots=True)
class SourceItem:
    source_name: str
    source_url: str
    title: str
    text: str
    category_hint: str | None = None
    published_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AIUpdate:
    category: str
    title: str
    summary: str
    confidence: float
    dedupe_key: str
    source_urls: list[str] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "text": self.summary,
            "updated_at": now_text(),
            "hash": self.dedupe_key,
            "sources": self.source_urls,
            "items": self.facts,
            "source_names": self.source_names,
            "confidence": self.confidence,
        }


def now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
