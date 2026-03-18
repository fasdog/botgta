import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import aiohttp
import discord
from bs4 import BeautifulSoup
from discord.ext import tasks

BASE_URL = "https://www.rockstargames.com"
NEWSWIRE_URL = f"{BASE_URL}/newswire"
STATE_PATH = Path("data/sent_posts.json")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
POST_ON_STARTUP = os.getenv("POST_ON_STARTUP", "false").lower() == "true"
MAX_ARTICLES_TO_SCAN = int(os.getenv("MAX_ARTICLES_TO_SCAN", "8"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("gta-news-bot")


class GTAOnlineNewswireBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.session: aiohttp.ClientSession | None = None
        self.has_finished_first_check = False

    async def setup_hook(self) -> None:
        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; GTAOnlineDiscordBot/1.0; +https://github.com/)"
            )
        }
        self.session = aiohttp.ClientSession(timeout=timeout, headers=headers)
        check_news.change_interval(minutes=CHECK_INTERVAL_MINUTES)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "?")
        if not check_news.is_running():
            check_news.start()

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()
        await super().close()


bot = GTAOnlineNewswireBot()


def ensure_state_dir() -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_sent_posts() -> set[str]:
    ensure_state_dir()
    if not STATE_PATH.exists():
        return set()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(str(x) for x in data)
    except Exception:
        logger.exception("Failed to read state file")
    return set()


def save_sent_posts(sent_posts: set[str]) -> None:
    ensure_state_dir()
    STATE_PATH.write_text(
        json.dumps(sorted(sent_posts), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def fetch_text(url: str) -> str:
    if not bot.session:
        raise RuntimeError("HTTP session is not ready")
    async with bot.session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def translate_text(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    if not DEEPL_API_KEY:
        return text

    if not bot.session:
        raise RuntimeError("HTTP session is not ready")

    async with bot.session.post(
        "https://api-free.deepl.com/v2/translate",
        headers={"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"},
        data={
            "text": text,
            "target_lang": "RU",
            "preserve_formatting": "1",
        },
    ) as response:
        response.raise_for_status()
        payload: dict[str, Any] = await response.json()
        translations = payload.get("translations") or []
        if not translations:
            return text
        return str(translations[0].get("text") or text)


async def fetch_article_links() -> list[str]:
    html = await fetch_text(NEWSWIRE_URL)
    soup = BeautifulSoup(html, "html.parser")

    links: list[str] = []
    seen: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if "/newswire/article/" not in href:
            continue
        full_url = urljoin(BASE_URL, href.split("?")[0])
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append(full_url)

    return links[:MAX_ARTICLES_TO_SCAN]


async def parse_article(url: str) -> dict[str, Any] | None:
    html = await fetch_text(url)
    soup = BeautifulSoup(html, "html.parser")

    full_text = soup.get_text(" ", strip=True)
    if "GTA Online" not in full_text:
        return None

    title = ""
    description = ""
    image_url = ""
    published = ""

    og_title = soup.find("meta", property="og:title")
    og_description = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")
    article_time = soup.find("time")

    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    if og_description and og_description.get("content"):
        description = og_description["content"].strip()
    if og_image and og_image.get("content"):
        image_url = og_image["content"].strip()
    if article_time:
        published = (article_time.get("datetime") or article_time.get_text(" ", strip=True)).strip()

    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else "Новая новость GTA Online"

    if not description:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        paragraphs = [p for p in paragraphs if len(p) > 80]
        description = paragraphs[0] if paragraphs else ""

    if not is_gta_online_article(title, description, full_text):
        return None

    clean_title = cleanup_meta_title(title)
    clean_description = cleanup_description(description)

    title_ru = await translate_text(clean_title)
    description_ru = await translate_text(clean_description[:1500]) if clean_description else ""

    return {
        "url": url,
        "title_en": clean_title,
        "title_ru": title_ru,
        "description_en": clean_description,
        "description_ru": description_ru,
        "image_url": image_url,
        "published": published,
    }


TITLE_SUFFIX_RE = re.compile(r"\s*[-|–—]\s*Rockstar Games\s*$", re.IGNORECASE)


def cleanup_meta_title(title: str) -> str:
    title = re.sub(TITLE_SUFFIX_RE, "", title or "").strip()
    return title



def cleanup_description(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:1000].rstrip()



def is_gta_online_article(title: str, description: str, full_text: str) -> bool:
    haystack = " ".join([title or "", description or "", full_text or ""]).lower()
    gta_score = 0
    for keyword in ["gta online", "grand theft auto online", "gta+", "los santos"]:
        if keyword in haystack:
            gta_score += 1
    return gta_score >= 1


async def build_embed(article: dict[str, Any]) -> discord.Embed:
    title = article["title_ru"] or article["title_en"]
    description = article["description_ru"] or article["description_en"] or "Новая новость по GTA Online."

    embed = discord.Embed(
        title=title[:256],
        url=article["url"],
        description=description[:4096],
    )

    if article.get("published"):
        embed.add_field(name="Дата", value=article["published"][:1024], inline=False)
    if article.get("title_en") and article["title_en"] != title:
        embed.add_field(name="Оригинальный заголовок", value=article["title_en"][:1024], inline=False)
    embed.add_field(name="Ссылка", value=f"[Открыть новость]({article['url']})", inline=False)
    embed.set_footer(text="Источник: Rockstar Games Newswire")

    image_url = article.get("image_url")
    if image_url:
        embed.set_image(url=image_url)

    return embed


@tasks.loop(minutes=30)
async def check_news() -> None:
    logger.info("Checking Rockstar Newswire for GTA Online updates...")

    if CHANNEL_ID == 0:
        logger.error("CHANNEL_ID is not set")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            fetched = await bot.fetch_channel(CHANNEL_ID)
            if isinstance(fetched, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
                channel = fetched
        except Exception:
            logger.exception("Failed to fetch channel by id")
            return

    if channel is None or not hasattr(channel, "send"):
        logger.error("Channel %s not found or unsupported", CHANNEL_ID)
        return

    sent_posts = load_sent_posts()

    try:
        links = await fetch_article_links()
        logger.info("Found %s candidate articles", len(links))
    except Exception:
        logger.exception("Failed to fetch article links")
        return

    new_articles: list[dict[str, Any]] = []

    for url in links:
        if url in sent_posts:
            continue
        try:
            article = await parse_article(url)
        except Exception:
            logger.exception("Failed to parse article: %s", url)
            continue
        if article:
            new_articles.append(article)
        await asyncio.sleep(1.0)

    if not new_articles:
        logger.info("No new GTA Online articles")
        bot.has_finished_first_check = True
        return

    new_articles.reverse()

    if not bot.has_finished_first_check and not POST_ON_STARTUP:
        for article in new_articles:
            sent_posts.add(article["url"])
        save_sent_posts(sent_posts)
        logger.info("Startup scan completed without posting old news (%s items saved)", len(new_articles))
        bot.has_finished_first_check = True
        return

    for article in new_articles:
        try:
            embed = await build_embed(article)
            await channel.send(embed=embed)
            sent_posts.add(article["url"])
            save_sent_posts(sent_posts)
            logger.info("Posted article: %s", article["title_en"])
            await asyncio.sleep(2.0)
        except Exception:
            logger.exception("Failed to send article to Discord: %s", article["url"])

    bot.has_finished_first_check = True


@check_news.before_loop
async def before_check_news() -> None:
    await bot.wait_until_ready()


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set")
    if CHANNEL_ID == 0:
        raise RuntimeError("CHANNEL_ID is not set")
    bot.run(DISCORD_TOKEN)
