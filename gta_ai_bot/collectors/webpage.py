from __future__ import annotations

import re

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


DATE_PATTERNS = [
    r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
    r"\d{1,2}\s+(?:янв|фев|мар|апр|май|мая|июн|июл|авг|сен|сент|окт|ноя|дек)",
]


def _clean_inline(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split()).strip()


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
    return line.lower().startswith(noise_starts)


def _smart_trim(text: str, limit: int = 3500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text

    cut = text[:limit]
    last_break = max(cut.rfind("\n\n"), cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if last_break > 500:
        cut = cut[:last_break].rstrip()

    return cut.rstrip() + "…"


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

        return []

    def _collect_steam_allnews(self, url: str, html: str) -> list[SourceItem]:
        soup = BeautifulSoup(html, "html.parser")
        raw_text = soup.get_text("\n", strip=True)

        lines = [_clean_inline(line) for line in raw_text.splitlines()]
        lines = [line for line in lines if line and not _looks_like_noise(line)]

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
        body_lines: list[str] = []

        for line in lines[date_idx + 1 :]:
            if _looks_like_noise(line):
                continue
            if line == "Grand Theft Auto V Legacy":
                break
            if _is_date_line(line):
                break
            if len(line) < 2:
                continue
            body_lines.append(line)

        if not title and not body_lines:
            return []

        paragraphs: list[str] = []
        current: list[str] = []

        for line in body_lines:
            is_heading = (
                len(line) <= 90 and (
                    line.isupper() or
                    line.endswith(":") or
                    ("GTA $" in line and len(line) <= 120)
                )
            )

            if is_heading:
                if current:
                    paragraphs.append(" ".join(current).strip())
                    current = []
                paragraphs.append(line.strip())
                continue

            current.append(line)

            if len(" ".join(current)) > 450:
                paragraphs.append(" ".join(current).strip())
                current = []

        if current:
            paragraphs.append(" ".join(current).strip())

        text = "\n\n".join(p for p in paragraphs if p).strip()
        text = _smart_trim(text, 3500)

        return [
            SourceItem(
                source_name=self.source_config.get("name", url),
                source_url=url,
                title=title,
                text=text,
                category_hint=self.source_config.get("category_hint", "news"),
            )
        ]
