from __future__ import annotations

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

        soup = BeautifulSoup(html, "html.parser")

        title_selector = self.source_config.get("title_selector")
        text_selector = self.source_config.get("text_selector")
        category_hint = self.source_config.get("category_hint")
        source_name = self.source_config.get("name", url)

        title_node = soup.select_one(title_selector) if title_selector else None
        text_node = soup.select_one(text_selector) if text_selector else None

        title = title_node.get_text(" ", strip=True) if title_node else ""
        text = text_node.get_text(" ", strip=True) if text_node else ""

        # режем слишком длинные страницы
        text = text[:12000]

        if not title and not text:
            return []

        return [
            SourceItem(
                source_name=source_name,
                source_url=url,
                title=title or source_name,
                text=text or title,
                category_hint=category_hint,
            )
        ]
