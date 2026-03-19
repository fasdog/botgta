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


def _clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


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

            if len(text) > 5000:
                text = text[:4997].rstrip() + "..."

            results.append(
                SourceItem(
                    source_name=source_name,
                    source_url=full_url,
                    title=title or source_name,
                    text=text or title,
                    category_hint=category_hint,
                )
            )

        return results
