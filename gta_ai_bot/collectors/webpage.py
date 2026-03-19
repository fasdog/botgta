from __future__ import annotations

import re
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from ..models import SourceItem


BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


def _clean_text(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split()).strip()


def _truncate(text: str, limit: int = 5000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


DATE_PATTERNS = [
    r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
    r"\d{1,2}\s+(?:янв|фев|мар|апр|ма[йя]|июн|июл|авг|сен|сент|окт|ноя|дек)",
]


def _is_date_line(line: str) -> bool:
    for pattern in DATE_PATTERNS:
        if re.fullmatch(pattern, line, flags=re.IGNORECASE):
            return True
    return False


def _looks_like_noise(line: str) -> bool:
    noise_starts = (
        "войти",
        "магазин",
        "главная",
        "рекомендации",
        "список желаемого",
        "предметы за очки",
        "новости",
        "чарты",
        "сообщество",
        "обсуждения",
        "мастерская",
        "торговая площадка",
        "трансляции",
        "информация",
        "поддержка",
        "изменить язык",
        "скачать мобильное приложение",
        "полная версия",
        "политика конфиденциальности",
        "правовая информация",
        "доступность",
        "соглашение подписчика steam",
        "возврат средств",
        "файлы cookie",
        "установить steam",
        "язык",
        "страница в магазине",
        "статистика:",
        "показать",
        "все новости",
        "публикации",
        "официальные объявления",
        "see full event details",
    )
    lower = line.lower()
    return lower.startswith(noise_starts)


class ConfiguredWebCollector:
    def __init__(self, session: aiohttp.ClientSession, source_config: dict):
        self.session = session
        self.source_config = source_config

    async def collect(self) -> list[SourceItem]:
        url = self.source_config["url"]

        async with self.session.get(url, headers=BROWSER_HEADERS) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()

        if "steamcommunity.com/app/" in url and "/allnews" in url:
            return self._collect_steam_allnews(url, html)

        return self._collect_generic(url, html)

    def _collect_generic(self, url: str, html: str) -> list[SourceItem]:
        soup = BeautifulSoup(html, "html.parser")

        list_selector = self.source_config.get("list_selector")
        item_selector = self.source_config.get("item_selector")
        title_selector = self.source_config.get("title_selector")
        text_selector = self.source_config.get("text_selector")
        link_selector = self.source_config.get("link_selector", "a")
        category_hint = self.source_config.get("category_hint")
        source_name = self.source_config.get("name", url)
        max_items = int(self.source_config.get("max_items", 10))

        scope = soup.select_one(list_selector) if list_selector else soup
        if scope is None:
            return []

        nodes = scope.select(item_selector) if item_selector else [scope]
        results: list[SourceItem] = []

        for node in nodes[:max_items]:
            title_node = node.select_one(title_selector) if title_selector else None
            text_node = node.select_one(text_selector) if text_selector else None
            link_node = node.select_one(link_selector) if link_selector else None

            title = _clean_text(title_node.get_text(" ", strip=True)) if title_node else ""
            text = _clean_text(text_node.get_text(" ", strip=True)) if text_node else ""

            href = ""
            if link_node is not None:
                href = (link_node.get("href") or "").strip()

            full_url = urljoin(url, href) if href else url

            if not title and not text:
                continue

            results.append(
                SourceItem(
                    source_name=source_name,
                    source_url=full_url,
                    title=title or source_name,
                    text=_truncate(text or title),
                    category_hint=category_hint,
                )
            )

        return results

    def _collect_steam_allnews(self, url: str, html: str) -> list[SourceItem]:
        soup = BeautifulSoup(html, "html.parser")
        raw_text = soup.get_text("\n", strip=True)
        lines = [_clean_text(line) for line in raw_text.splitlines()]
        lines = [line for line in lines if line and not _looks_like_noise(line)]

        category_hint = self.source_config.get("category_hint")
        source_name = self.source_config.get("name", url)

        title_idx = None
        date_idx = None

        for i, line in enumerate(lines):
            if _is_date_line(line):
                if i > 0 and len(lines[i - 1]) > 8:
                    title_idx = i - 1
                    date_idx = i
                    break

        if title_idx is None or date_idx is None:
            return []

        title = lines[title_idx]
        body_parts: list[str] = []

        for line in lines[date_idx + 1 :]:
            if _looks_like_noise(line):
                continue
            if line == "Grand Theft Auto V Legacy":
                break
            if _is_date_line(line):
                break
            if len(line) < 3:
                continue
            body_parts.append(line)

        body = _truncate(_clean_text(" ".join(body_parts)))

        if not title and not body:
            return []

        return [
            SourceItem(
                source_name=source_name,
                source_url=url,
                title=title or source_name,
                text=body or title,
                category_hint=category_hint,
            )
        ]
