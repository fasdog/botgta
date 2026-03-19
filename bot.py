
import os
import re
import json
import html
import asyncio
import hashlib
from datetime import datetime, timezone

import aiohttp
import discord
from bs4 import BeautifulSoup
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
SEND_STARTUP_MESSAGE = os.getenv("SEND_STARTUP_MESSAGE", "true").lower() == "true"
ROLE_PING_ID = os.getenv("ROLE_PING_ID", "").strip()
DEEPL_API_KEY = os.getenv("DEEPL_API_KEY", "").strip()
DEEPL_API_URL = os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate").strip()

STATE_FILE = "state.json"

NEWSWIRE_URL = "https://www.rockstargames.com/newswire"
TRACKER_URLS = {
    "gun_van": "https://gtalens.com/map/gun-vans",
    "street_dealers": "https://gtalens.com/map/street-dealers",
    "stash_house": "https://gtalens.com/map/stash-houses",
    "shipwreck": "https://gtalens.com/map/shipwrecks",
    "hidden_caches": "https://gtalens.com/map/hidden-caches",
}

TRACKER_META = {
    "gun_van": {"title": "🔫 Фургон с оружием", "color": 0xF39C12},
    "street_dealers": {"title": "💊 Уличные дилеры", "color": 0x2ECC71},
    "stash_house": {"title": "🏠 Дом-тайник", "color": 0x3498DB},
    "shipwreck": {"title": "🚢 Кораблекрушение", "color": 0x1ABC9C},
    "hidden_caches": {"title": "🌊 Скрытые тайники", "color": 0x9B59B6},
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

session: aiohttp.ClientSession | None = None


def default_state():
    return {
        "sent_news_links": [],
        "tracker_hashes": {},
        "started_once": False,
        "last_summary": {},
    }


def load_state():
    if not os.path.exists(STATE_FILE):
        return default_state()
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = default_state()
        base.update(data)
        return base
    except Exception:
        return default_state()


def save_state():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


state = load_state()


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def chunk_text(text: str, size: int = 4500):
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def lines_from_html(raw_html: str):
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [compact(x) for x in text.splitlines()]
    return [x for x in lines if x]


async def ensure_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(headers={
            "User-Agent": "Mozilla/5.0 GTA-Discord-Bot-Ultra/3.0"
        })


async def fetch_text(url: str) -> str:
    await ensure_session()
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=40)) as resp:
        resp.raise_for_status()
        return await resp.text()


async def deepl_translate(text: str) -> str:
    if not text or not DEEPL_API_KEY:
        return text

    await ensure_session()
    try:
        data = {
            "text": text,
            "target_lang": "RU",
        }
        headers = {"Authorization": f"DeepL-Auth-Key {DEEPL_API_KEY}"}
        async with session.post(DEEPL_API_URL, data=data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return text
            payload = await resp.json()
            translations = payload.get("translations", [])
            if not translations:
                return text
            return translations[0].get("text", text)
    except Exception:
        return text


async def maybe_translate_news_title(title: str) -> str:
    if not DEEPL_API_KEY:
        return title
    translated = await deepl_translate(title)
    return translated or title


class LinkView(discord.ui.View):
    def __init__(self, url: str, label: str = "Открыть"):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=label, url=url))


def ping_text():
    return f"<@&{ROLE_PING_ID}>" if ROLE_PING_ID else None


def relevant_lines(lines, keywords, max_lines=8):
    out = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in keywords):
            if line not in out:
                out.append(line)
        if len(out) >= max_lines:
            break
    return out


def clean_tracker_lines(lines, limit=8):
    cleaned = []
    bad = ["cookie", "privacy", "terms", "sign in", "join discord", "login", "advertisement"]
    for line in lines:
        low = line.lower()
        if any(x in low for x in bad):
            continue
        if len(line) < 2:
            continue
        if line not in cleaned:
            cleaned.append(line)
        if len(cleaned) >= limit:
            break
    return cleaned


async def fetch_news_items():
    html_text = await fetch_text(NEWSWIRE_URL)
    soup = BeautifulSoup(html_text, "html.parser")
    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        title = compact(a.get_text(" ", strip=True))
        href = a["href"]
        if not title:
            continue

        title_low = title.lower()
        if "gta" not in title_low and "online" not in title_low:
            continue

        if not href.startswith("http"):
            href = "https://www.rockstargames.com" + href

        if href in seen:
            continue
        seen.add(href)

        items.append({
            "title": title[:250],
            "url": href,
        })

    return items[:12]


async def parse_tracker(key: str):
    html_text = await fetch_text(TRACKER_URLS[key])
    lines = lines_from_html(html_text)

    keyword_sets = {
        "gun_van": ["gun van", "location", "weapon", "inventory", "discount", "railgun", "today", "available"],
        "street_dealers": ["street dealer", "dealer", "location", "today", "weed", "cocaine", "meth", "lsd"],
        "stash_house": ["stash house", "location", "today", "daily", "raid"],
        "shipwreck": ["shipwreck", "location", "today", "daily", "outfit"],
        "hidden_caches": ["hidden cache", "cache", "location", "today", "daily"],
    }

    useful = relevant_lines(lines, keyword_sets[key], max_lines=12)
    useful = clean_tracker_lines(useful or lines[:12], limit=10)

    meta = TRACKER_META[key]
    description = "\n".join(f"• {line}" for line in useful[:10]) or "Открой карту по ссылке ниже."
    raw = " | ".join(useful[:14]) or key

    state["last_summary"][key] = useful[:10]
    return {
        "key": key,
        "title": meta["title"],
        "description": description,
        "url": TRACKER_URLS[key],
        "raw": raw,
        "color": meta["color"],
    }


def make_embed(title: str, description: str, url: str, color: int):
    embed = discord.Embed(
        title=title,
        description=description[:4096],
        url=url,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="GTA Online Ultra Bot")
    return embed


async def send_embed(channel: discord.abc.Messageable, title: str, description: str, url: str, color: int, mention_role: bool = False):
    content = ping_text() if mention_role else None
    embed = make_embed(title, description, url, color)
    view = LinkView(url, "Открыть карту" if "map" in url else "Открыть новость")
    await channel.send(content=content, embed=embed, view=view)


async def post_startup_message(channel: discord.TextChannel):
    if not SEND_STARTUP_MESSAGE or state.get("started_once"):
        return

    embed = discord.Embed(
        title="✅ Бот запущен",
        description=(
            "Я онлайн и автоматически проверяю:\n"
            "• новости GTA Online\n"
            "• фургон с оружием\n"
            "• уличных дилеров\n"
            "• дом-тайник\n"
            "• кораблекрушение\n"
            "• скрытые тайники\n\n"
            "Команды:\n"
            "`!gta` `!gunvan` `!dealers` `!stash` `!shipwreck` `!caches` `!status` `!help`"
        ),
        color=0x57F287,
        timestamp=datetime.now(timezone.utc),
    )
    await channel.send(embed=embed)
    state["started_once"] = True
    save_state()


async def check_news(channel: discord.TextChannel):
    try:
        news = await fetch_news_items()
        changed = False

        for item in reversed(news):
            if item["url"] in state["sent_news_links"]:
                continue

            title_ru = await maybe_translate_news_title(item["title"])
            await send_embed(
                channel,
                f"📰 {title_ru}",
                "Новая новость GTA Online.",
                item["url"],
                0x5865F2,
                mention_role=bool(ROLE_PING_ID),
            )
            state["sent_news_links"].append(item["url"])
            changed = True
            await asyncio.sleep(2)

        if len(state["sent_news_links"]) > 300:
            state["sent_news_links"] = state["sent_news_links"][-300:]

        if changed:
            save_state()
    except Exception as e:
        print("NEWS ERROR:", e)


async def check_trackers(channel: discord.TextChannel):
    changed = False
    for key in TRACKER_URLS:
        try:
            info = await parse_tracker(key)
            current = short_hash(info["raw"])
            previous = state["tracker_hashes"].get(key)

            if current != previous:
                await send_embed(
                    channel,
                    info["title"],
                    info["description"],
                    info["url"],
                    info["color"],
                    mention_role=False,
                )
                state["tracker_hashes"][key] = current
                changed = True
                await asyncio.sleep(2)
        except Exception as e:
            print(f"TRACKER ERROR [{key}]:", e)

    if changed:
        save_state()


async def full_check(channel: discord.abc.Messageable):
    if isinstance(channel, discord.TextChannel):
        await check_news(channel)
        await check_trackers(channel)


def status_text():
    parts = [
        f"Интервал проверки: {CHECK_INTERVAL} мин.",
        f"Роль-пинг: {'включён' if ROLE_PING_ID else 'выключен'}",
        f"Авто-старт сообщение: {'включено' if SEND_STARTUP_MESSAGE else 'выключено'}",
        f"Новостей сохранено: {len(state.get('sent_news_links', []))}",
    ]
    return "\n".join(f"• {x}" for x in parts)


async def loop_task():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)

    if channel is None:
        print("ERROR: Channel not found. Проверь CHANNEL_ID.")
        return

    await post_startup_message(channel)
    await check_news(channel)
    await check_trackers(channel)

    while not bot.is_closed():
        await asyncio.sleep(CHECK_INTERVAL * 60)
        await check_news(channel)
        await check_trackers(channel)


@bot.command()
async def gta(ctx):
    await ctx.send("Проверяю всё...")
    await full_check(ctx.channel)
    await ctx.send("Готово.")


@bot.command()
async def gunvan(ctx):
    info = await parse_tracker("gun_van")
    await send_embed(ctx.channel, info["title"], info["description"], info["url"], info["color"])


@bot.command()
async def dealers(ctx):
    info = await parse_tracker("street_dealers")
    await send_embed(ctx.channel, info["title"], info["description"], info["url"], info["color"])


@bot.command()
async def stash(ctx):
    info = await parse_tracker("stash_house")
    await send_embed(ctx.channel, info["title"], info["description"], info["url"], info["color"])


@bot.command()
async def shipwreck(ctx):
    info = await parse_tracker("shipwreck")
    await send_embed(ctx.channel, info["title"], info["description"], info["url"], info["color"])


@bot.command()
async def caches(ctx):
    info = await parse_tracker("hidden_caches")
    await send_embed(ctx.channel, info["title"], info["description"], info["url"], info["color"])


@bot.command()
async def status(ctx):
    embed = discord.Embed(
        title="📊 Статус бота",
        description=status_text(),
        color=0x95A5A6,
        timestamp=datetime.now(timezone.utc),
    )
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="❓ Команды",
        description=(
            "`!gta` — проверить всё\n"
            "`!gunvan` — фургон с оружием\n"
            "`!dealers` — дилеры\n"
            "`!stash` — дом-тайник\n"
            "`!shipwreck` — кораблекрушение\n"
            "`!caches` — скрытые тайники\n"
            "`!status` — статус бота"
        ),
        color=0x7289DA,
    )
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    bot.loop.create_task(loop_task())


async def close_session():
    global session
    if session and not session.closed:
        await session.close()


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

try:
    bot.run(TOKEN)
finally:
    try:
        asyncio.run(close_session())
    except Exception:
        pass
