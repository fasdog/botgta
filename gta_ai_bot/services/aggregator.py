from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Iterable

from ..models import AIUpdate, SourceItem
from .openai_client import OpenAIResponsesClient

ALLOWED_CATEGORIES = {"gunvan", "dealers", "stash", "shipwreck", "caches", "news", "weekly"}


class GTAAIAggregator:
    def __init__(self, client: OpenAIResponsesClient, max_source_text_chars: int = 4000):
        self.client = client
        self.max_source_text_chars = max_source_text_chars

    async def summarize(self, items: Iterable[SourceItem]) -> list[AIUpdate]:
        normalized = [item.to_dict() for item in items]
        if not normalized:
            return []

        prompt = self._build_prompt(normalized)
        payload = await self.client.create_json_response(prompt)
        updates = payload.get("updates", [])
        results: list[AIUpdate] = []
        for update in updates:
            category = str(update.get("category", "")).strip().lower()
            summary = str(update.get("summary", "")).strip()
            if category not in ALLOWED_CATEGORIES or not summary:
                continue

            source_urls = [str(x) for x in update.get("source_urls", []) if str(x).strip()]
            source_names = [str(x) for x in update.get("source_names", []) if str(x).strip()]
            facts = [str(x).strip() for x in update.get("facts", []) if str(x).strip()]
            dedupe_basis = json.dumps(
                {
                    "category": category,
                    "summary": summary,
                    "source_urls": sorted(set(source_urls)),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            dedupe_key = hashlib.sha256(dedupe_basis.encode("utf-8")).hexdigest()
            results.append(
                AIUpdate(
                    category=category,
                    title=str(update.get("title", "")).strip() or category.upper(),
                    summary=summary,
                    confidence=float(update.get("confidence", 0.0) or 0.0),
                    dedupe_key=dedupe_key,
                    source_urls=list(dict.fromkeys(source_urls)),
                    source_names=list(dict.fromkeys(source_names)),
                    facts=facts,
                )
            )
        return results

    def _build_prompt(self, items: list[dict]) -> str:
        compact_items = []
        for item in items:
            compact_items.append(
                {
                    "source_name": item["source_name"],
                    "source_url": item["source_url"],
                    "title": item["title"][:300],
                    "text": item["text"][: self.max_source_text_chars],
                    "category_hint": item.get("category_hint"),
                    "published_at": item.get("published_at"),
                }
            )

        instruction = {
            "task": "Ты GTA Online news analyst. Из списка сырых источников выдели только реальные обновления по GTA Online и разложи их по категориям.",
            "rules": [
                "Верни JSON с ключом updates.",
                "Категории только: gunvan, dealers, stash, shipwreck, caches, news, weekly.",
                "Игнорируй сомнительные, дублирующиеся и нерелевантные записи.",
                "Пиши summary на русском языке, в формате, готовом для Discord embed.",
                "summary должен быть кратким, фактическим и без выдумок.",
                "Если источник не подтверждает конкретное обновление, не включай его.",
                "facts — короткие подтверждающие пункты без воды.",
                "confidence — число от 0 до 1.",
                "source_urls и source_names должны соответствовать использованным источникам.",
                "Если weekly update найден, отделяй weekly от general news.",
            ],
            "output_schema": {
                "updates": [
                    {
                        "category": "weekly",
                        "title": "Короткий заголовок",
                        "summary": "Discord-ready summary",
                        "confidence": 0.95,
                        "source_urls": ["https://..."],
                        "source_names": ["Rockstar Newswire RSS"],
                        "facts": ["Пункт 1", "Пункт 2"],
                    }
                ]
            },
            "items": compact_items,
        }
        return json.dumps(instruction, ensure_ascii=False)


def group_items_by_hint(items: list[SourceItem]) -> dict[str, list[SourceItem]]:
    grouped: dict[str, list[SourceItem]] = defaultdict(list)
    for item in items:
        grouped[item.category_hint or "unknown"].append(item)
    return grouped
