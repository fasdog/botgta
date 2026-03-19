from __future__ import annotations

from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from ..models import SourceItem


class ConfiguredWebCollector:
    def __init__(self, session: aiohttp.ClientSession, source_config: dict):
        self.session = session
        self.source_config = source_config

    async def collect(self) -> list[SourceItem]:
        url = self.source_config["url"]
        async with self.session.get(url) as resp:
            resp.raise_for_status()
            html = await resp.text()

        soup = BeautifulSoup(html, "html.parser")
        list_selector = self.source_config.get("list_selector")
        item_selector = self.source_config.get("item_selector")
        title_selector = self.source_config.get("title_selector")
        text_selector = self.source_config.get("text_selector")
        link_selector = self.source_config.get("link_selector", "a")
        category_hint = self.source_config.get("category_hint")
        source_name = self.source_config.get("name", url)

        scope = soup.select_one(list_selector) if list_selector else soup
        if scope is None:
            return []

        nodes = scope.select(item_selector) if item_selector else [scope]
        results: list[SourceItem] = []
        for node in nodes[: self.source_config.get("max_items", 10)]:
            title_node = node.select_one(title_selector) if title_selector else node
            text_node = node.select_one(text_selector) if text_selector else node
            link_node = node.select_one(link_selector) if link_selector else None

            title = title_node.get_text(" ", strip=True) if title_node else ""
            text = text_node.get_text(" ", strip=True) if text_node else ""
            href = link_node.get("href", "").strip() if link_node else url
            full_url = urljoin(url, href) if href else url
            if not title and not text:
                continue
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
