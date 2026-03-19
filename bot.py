
import os
import re
import json
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
    "gun_van": "https://gtaweb.eu/gtao-map/ls/2",
    "street_dealers": "https://gtaweb.eu/gtao-map/ls/hio94mrrlk3k",
    "stash_house": "https://gtaweb.eu/gtao-map/ls/-/stash-houses",
    "shipwreck": "https://gtaweb.eu/gtao-map/ls/-/shipwrecks",
    "hidden_caches": "https://gtaweb.eu/gtao-map/ls/-/hidden-caches",
}

TRACKER_META = {
    "gun_van": {"title": "🔫 Фургон с оружием", "color": 0xF39C12, "button": "Открыть карту Gun Van"},
    "street_dealers": {"title": "💊 Уличные дилеры", "color": 0x2ECC71, "button": "Открыть карту дилеров"},
    "stash_house": {"title": "🏠 Дом-тайник", "color": 0x3498DB, "button": "Открыть карту тайников"},
    "shipwreck": {"title": "🚢 Кораблекрушение", "color": 0x1ABC9C, "button": "Открыть карту Shipwreck"},
    "hidden_caches": {"title": "🌊 Скрытые тайники", "color": 0x9B59B6, "button": "Открыть карту тайников"},
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

session = None


def default_state():
    return {
        "sent_news_links": [],
        "tracker_hashes": {},
        "started_once": False,
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


def short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def ensure_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
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
        data = {"text": text, "target_lang": "RU"}
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


class LinkView(discord.ui.View):
    def __init__(self, url: str, label: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=label, url=url))


def ping_text():
    return f"<@&{ROLE_PING_ID}>" if ROLE_PING_ID else None


def make_embed(title: str, description: str, url: str, color: int):
    embed = discord.Embed(
        title=title,
        description=description[:4096],
        url=url,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="GTA Online Bot")
    return embed


async def send_embed(channel, title: str, description: str, url: str, color: int, button_label: str, mention_role: bool = False):
    content = ping_text() if mention_role else None
    embed = make_embed(title, description, url, color)
    await channel.send(content=content, embed=embed, view=LinkView(url, button_label))


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
        low = title.lower()
        if "gta" not in low and "online" not in low:
            continue
        if not href.startswith("http"):
            href = "https://www.rockstargames.com" + href
        if href in seen:
            continue
        seen.add(href)
        items.append({"title": title[:250], "url": href})

    return items[:12]


def extract_candidate_lines(html_text: str):
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [compact(x) for x in text.splitlines()]
    lines = [x for x in lines if x]

    cleaned = []
    bad = [
        "privacy policy", "supporters list", "suggestions & issues", "buy me a coffee",
        "tampermonkey", "services status", "register", "login", "resend activation email",
        "remind password", "website translation", "home", "gta online toolkit"
    ]
    for line in lines:
        low = line.lower()
        if any(b in low for b in bad):
            continue
        if line not in cleaned:
            cleaned.append(line)
    return cleaned


def pick_lines(lines, keywords, limit=10):
    out = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in keywords):
            if line not in out:
                out.append(line)
        if len(out) >= limit:
            break

    if not out:
        out = lines[:limit]
    return out[:limit]


async def parse_tracker(key: str):
    html_text = await fetch_text(TRACKER_URLS[key])
    lines = extract_candidate_lines(html_text)

    keyword_sets = {
        "gun_van": ["gun van", "weapon", "inventory", "discount", "location", "today", "available"],
        "street_dealers": ["street dealer", "dealer", "location", "today", "weed", "cocaine", "meth", "lsd"],
        "stash_house": ["stash", "house", "location", "today", "daily"],
        "shipwreck": ["shipwreck", "location", "today", "daily", "outfit"],
        "hidden_caches": ["hidden cache", "cache", "location", "today", "daily"],
    }

    picked = pick_lines(lines, keyword_sets[key], limit=10)
    meta = TRACKER_META[key]
    description = "\n".join(f"• {x}" for x in picked) or "Открой карту по ссылке ниже."
    raw = " | ".join(picked) or key

    return {
        "title": meta["title"],
        "description": description,
        "url": TRACKER_URLS[key],
        "raw": raw,
        "color": meta["color"],
        "button": meta["button"],
    }


async def post_startup_message(channel):
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


async def check_news(channel):
    try:
        news = await fetch_news_items()
        changed = False
        for item in reversed(news):
            if item["url"] in state["sent_news_links"]:
                continue
            title_ru = await deepl_translate(item["title"])
            await send_embed(
                channel,
                f"📰 {title_ru}",
                "Новая новость GTA Online.",
                item["url"],
                0x5865F2,
                "Открыть новость",
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


async def check_trackers(channel):
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
                    info["button"],
                )
                state["tracker_hashes"][key] = current
                changed = True
                await asyncio.sleep(2)
        except Exception as e:
            print(f"TRACKER ERROR [{key}]:", e)

    if changed:
        save_state()


async def tracker_command(ctx, key: str):
    try:
        info = await parse_tracker(key)
        await send_embed(ctx.channel, info["title"], info["description"], info["url"], info["color"], info["button"])
    except Exception as e:
        await ctx.send(f"Не удалось получить данные: `{type(e).__name__}`. Попробуй позже.")


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
    await check_news(ctx.channel)
    await check_trackers(ctx.channel)
    await ctx.send("Готово.")


@bot.command()
async def gunvan(ctx):
    await tracker_command(ctx, "gun_van")


@bot.command()
async def dealers(ctx):
    await tracker_command(ctx, "street_dealers")


@bot.command()
async def stash(ctx):
    await tracker_command(ctx, "stash_house")


@bot.command()
async def shipwreck(ctx):
    await tracker_command(ctx, "shipwreck")


@bot.command()
async def caches(ctx):
    await tracker_command(ctx, "hidden_caches")


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
