from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from ..models import SourceItem


def _clean_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _detect_category(item: SourceItem) -> str:
    hint = (item.category_hint or "").strip().lower()
    if hint:
        return hint

    text = f"{item.title} {item.text}".lower()

    weekly_markers = [
        "gta online bonuses",
        "bonuses and discounts",
        "weekly",
        "event week",
        "на этой неделе",
        "бонусы",
        "скидки",
    ]
    if any(marker in text for marker in weekly_markers):
        return "weekly"

    return "news"


@dataclass
class AggregatedUpdate:
    category: str
    title: str
    text: str
    source_name: str
    source_url: str
    dedupe_key: str
    sources: list[str] = field(default_factory=list)
    confidence: float = 1.0
    facts: list[str] = field(default_factory=list)

    def to_storage_dict(self) -> dict:
        return {
            "title": self.title,
            "text": self.text,
            "hash": self.dedupe_key,
            "sources": self.sources or [self.source_url],
            "confidence": self.confidence,
            "facts": self.facts,
            "source_url": self.source_url,
            "source_name": self.source_name,
        }


class GTAAIAggregator:
    def __init__(self, max_source_text_chars: int = 12000):
        self.max_source_text_chars = max_source_text_chars

    async def summarize(self, items: list[SourceItem]) -> list[AggregatedUpdate]:
        updates: list[AggregatedUpdate] = []

        for item in items:
            category = _detect_category(item)

            title = _clean_text(item.title or item.source_name or "GTA Update")
            text = _clean_text(item.text or item.title or "")

            if not text and not title:
                continue

            text = _truncate(text, self.max_source_text_chars)

            raw = f"{category}\n{title}\n{text}\n{item.source_url}"
            dedupe_key = hashlib.sha256(raw.encode("utf-8")).hexdigest()

            updates.append(
                AggregatedUpdate(
                    category=category,
                    title=title,
                    text=text,
                    source_name=item.source_name,
                    source_url=item.source_url,
                    dedupe_key=dedupe_key,
                    sources=[item.source_url],
                    confidence=1.0,
                    facts=[],
                )
            )

        return updates
