from __future__ import annotations

import email.utils
from datetime import timezone
from xml.etree import ElementTree

import aiohttp
from bs4 import BeautifulSoup

from ..models import SourceItem


class NewswireRSSCollector:
    def __init__(self, session: aiohttp.ClientSession, url: str):
        self.session = session
        self.url = url

    async def collect(self) -> list[SourceItem]:
        async with self.session.get(self.url) as resp:
            resp.raise_for_status()
            xml_text = await resp.text()

        root = ElementTree.fromstring(xml_text)
        items: list[SourceItem] = []
        for node in root.findall(".//item")[:10]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            description_html = node.findtext("description") or ""
            description_text = BeautifulSoup(description_html, "html.parser").get_text(" ", strip=True)
            pub_date = node.findtext("pubDate")
            published_at = None
            if pub_date:
                dt = email.utils.parsedate_to_datetime(pub_date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                published_at = dt.astimezone(timezone.utc).isoformat()
            if title and link:
                items.append(
                    SourceItem(
                        source_name="Rockstar Newswire RSS",
                        source_url=link,
                        title=title,
                        text=description_text or title,
                        category_hint="news",
                        published_at=published_at,
                    )
                )
        return items
