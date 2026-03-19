
import os
import json
import asyncio
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

TRACKERS = {
    "gunvan": {
        "title": "🔫 Фургон с оружием",
        "desc": "Открыть актуальную карту фургона с оружием.",
        "url": "https://gtaweb.eu/gtao-map/ls/2",
        "color": 0xF39C12,
        "button": "Открыть Gun Van",
    },
    "dealers": {
        "title": "💊 Уличные дилеры",
        "desc": "Открыть актуальную карту уличных дилеров.",
        "url": "https://gtaweb.eu/gtao-map/ls/hio94mrrlk3k",
        "color": 0x2ECC71,
        "button": "Открыть дилеров",
    },
    "stash": {
        "title": "🏠 Дом-тайник",
        "desc": "Открыть актуальную карту домов-тайников.",
        "url": "https://gtaweb.eu/gtao-map/ls/-/stash-houses",
        "color": 0x3498DB,
        "button": "Открыть тайники",
    },
    "shipwreck": {
        "title": "🚢 Кораблекрушение",
        "desc": "Открыть актуальную карту кораблекрушения.",
        "url": "https://gtaweb.eu/gtao-map/ls/-/shipwrecks",
        "color": 0x1ABC9C,
        "button": "Открыть Shipwreck",
    },
    "caches": {
        "title": "🌊 Скрытые тайники",
        "desc": "Открыть актуальную карту скрытых тайников.",
        "url": "https://gtaweb.eu/gtao-map/ls/-/hidden-caches",
        "color": 0x9B59B6,
        "button": "Открыть тайники",
    },
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

session = None


def default_state():
    return {
        "sent_news_links": [],
        "started_once": False,
        "last_daily_digest_date": "",
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


async def ensure_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(headers={
            "User-Agent": "Mozilla/5.0 GTA-Discord-Bot-Compact/1.0",
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


class MultiLinkView(discord.ui.View):
    def __init__(self, links: list[tuple[str, str]]):
        super().__init__(timeout=None)
        for label, url in links[:5]:
            self.add_item(discord.ui.Button(label=label, url=url))


class SingleLinkView(discord.ui.View):
    def __init__(self, label: str, url: str):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=label, url=url))


def ping_text():
    return f"<@&{ROLE_PING_ID}>" if ROLE_PING_ID else None


def make_embed(title: str, description: str, color: int, url: str | None = None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc),
        url=url,
    )
    embed.set_footer(text="GTA Online Bot")
    return embed


async def send_tracker_embed(channel, key: str):
    t = TRACKERS[key]
    embed = make_embed(t["title"], t["desc"], t["color"], t["url"])
    await channel.send(embed=embed, view=SingleLinkView(t["button"], t["url"]))


async def send_dashboard(channel):
    embed = make_embed(
        "🎮 GTA Online — быстрый доступ",
        (
            "Нажми нужную кнопку ниже.\n\n"
            "Это компактный режим: вместо сырого текста с сайтов бот даёт быстрые ссылки на актуальные карты.\n"
            "Новости Rockstar бот продолжает публиковать автоматически."
        ),
        0x5865F2,
    )
    embed.add_field(name="🔫 Фургон с оружием", value="Актуальная карта Gun Van", inline=False)
    embed.add_field(name="💊 Уличные дилеры", value="Актуальная карта дилеров", inline=False)
    embed.add_field(name="🏠 Дом-тайник", value="Актуальная карта stash house", inline=False)
    embed.add_field(name="🚢 Кораблекрушение", value="Актуальная карта shipwreck", inline=False)
    embed.add_field(name="🌊 Скрытые тайники", value="Актуальная карта caches", inline=False)
    links = [
        (TRACKERS["gunvan"]["button"], TRACKERS["gunvan"]["url"]),
        (TRACKERS["dealers"]["button"], TRACKERS["dealers"]["url"]),
        (TRACKERS["stash"]["button"], TRACKERS["stash"]["url"]),
        (TRACKERS["shipwreck"]["button"], TRACKERS["shipwreck"]["url"]),
        (TRACKERS["caches"]["button"], TRACKERS["caches"]["url"]),
    ]
    await channel.send(embed=embed, view=MultiLinkView(links))


async def fetch_news_items():
    html = await fetch_text(NEWSWIRE_URL)
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text(" ", strip=True).split())
        href = a.get("href")
        if not title or not href:
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


async def check_news(channel):
    try:
        items = await fetch_news_items()
        changed = False
        for item in reversed(items):
            if item["url"] in state["sent_news_links"]:
                continue
            title = await deepl_translate(item["title"])
            embed = make_embed(
                f"📰 {title}",
                "Новая новость GTA Online.",
                0x5865F2,
                item["url"],
            )
            await channel.send(
                content=ping_text() if ROLE_PING_ID else None,
                embed=embed,
                view=SingleLinkView("Открыть новость", item["url"]),
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


async def maybe_send_daily_digest(channel):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("last_daily_digest_date") == today:
        return
    await send_dashboard(channel)
    state["last_daily_digest_date"] = today
    save_state()


async def post_startup_message(channel):
    if not SEND_STARTUP_MESSAGE or state.get("started_once"):
        return

    embed = make_embed(
        "✅ Бот запущен",
        (
            "Я онлайн.\n\n"
            "Автоматически публикую:\n"
            "• новости GTA Online\n\n"
            "По командам доступны:\n"
            "`!gta` `!gunvan` `!dealers` `!stash` `!shipwreck` `!caches` `!status` `!help`\n\n"
            "Трекеры теперь в компактном виде — без перегруженного текста."
        ),
        0x57F287,
    )
    await channel.send(embed=embed)
    state["started_once"] = True
    save_state()


def status_text():
    return (
        f"• Интервал проверки: {CHECK_INTERVAL} мин.\n"
        f"• Роль-пинг: {'включён' if ROLE_PING_ID else 'выключен'}\n"
        f"• Стартовое сообщение: {'включено' if SEND_STARTUP_MESSAGE else 'выключено'}\n"
        f"• Новостей сохранено: {len(state.get('sent_news_links', []))}"
    )


async def loop_task():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("ERROR: Channel not found. Проверь CHANNEL_ID.")
        return

    await post_startup_message(channel)
    await maybe_send_daily_digest(channel)
    await check_news(channel)

    while not bot.is_closed():
        await asyncio.sleep(CHECK_INTERVAL * 60)
        await maybe_send_daily_digest(channel)
        await check_news(channel)


@bot.command()
async def gta(ctx):
    await send_dashboard(ctx.channel)


@bot.command()
async def gunvan(ctx):
    await send_tracker_embed(ctx.channel, "gunvan")


@bot.command()
async def dealers(ctx):
    await send_tracker_embed(ctx.channel, "dealers")


@bot.command()
async def stash(ctx):
    await send_tracker_embed(ctx.channel, "stash")


@bot.command()
async def shipwreck(ctx):
    await send_tracker_embed(ctx.channel, "shipwreck")


@bot.command()
async def caches(ctx):
    await send_tracker_embed(ctx.channel, "caches")


@bot.command()
async def status(ctx):
    embed = make_embed("📊 Статус бота", status_text(), 0x95A5A6)
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    embed = make_embed(
        "❓ Команды",
        (
            "`!gta` — панель со всеми картами\n"
            "`!gunvan` — фургон с оружием\n"
            "`!dealers` — дилеры\n"
            "`!stash` — дом-тайник\n"
            "`!shipwreck` — кораблекрушение\n"
            "`!caches` — скрытые тайники\n"
            "`!status` — статус бота"
        ),
        0x7289DA,
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
