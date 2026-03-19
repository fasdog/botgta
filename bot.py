
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

STATE_FILE = "state.json"

NEWSWIRE_URL = "https://www.rockstargames.com/newswire"
TRACKER_URLS = {
    "gun_van": "https://gtalens.com/map/gun-vans",
    "street_dealers": "https://gtalens.com/map/street-dealers",
    "stash_house": "https://gtalens.com/map/stash-houses",
    "shipwreck": "https://gtalens.com/map/shipwrecks",
    "hidden_caches": "https://gtalens.com/map/hidden-caches",
}

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

session: aiohttp.ClientSession | None = None


def load_state():
    if not os.path.exists(STATE_FILE):
        return {"sent_news_links": [], "tracker_hashes": {}, "started_once": False}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sent_news_links": [], "tracker_hashes": {}, "started_once": False}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


state = load_state()


async def fetch_text(url: str) -> str:
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(headers={
            "User-Agent": "Mozilla/5.0 GTA-Discord-Bot/2.0"
        })
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        resp.raise_for_status()
        return await resp.text()


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_lines(soup: BeautifulSoup):
    raw = soup.get_text("\n", strip=True)
    lines = [compact(x) for x in raw.splitlines()]
    lines = [x for x in lines if x]
    return lines


async def fetch_news_items():
    html = await fetch_text(NEWSWIRE_URL)
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()

    for a in soup.find_all("a", href=True):
        title = compact(a.get_text(" ", strip=True))
        href = a["href"]

        if not title:
            continue

        t = title.lower()
        if "gta" not in t and "online" not in t:
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

    return items[:10]


def take_relevant_lines(lines, keywords, max_lines=8):
    out = []
    for line in lines:
        low = line.lower()
        if any(k in low for k in keywords):
            out.append(line)
        if len(out) >= max_lines:
            break
    return out


async def parse_gun_van():
    html = await fetch_text(TRACKER_URLS["gun_van"])
    soup = BeautifulSoup(html, "html.parser")
    lines = text_lines(soup)

    useful = take_relevant_lines(
        lines,
        ["gun van", "location", "weapon", "discount", "today", "available", "inventory", "railgun", "rifle"]
    )

    if not useful:
        useful = lines[:8]

    desc = "\n".join(f"• {x}" for x in useful[:8])
    raw = " | ".join(useful[:12])

    return {
        "title": "🔫 Фургон с оружием",
        "description": desc or "Открой карту по ссылке ниже.",
        "url": TRACKER_URLS["gun_van"],
        "raw": raw or "gun_van",
        "color": 0xF39C12,
    }


async def parse_street_dealers():
    html = await fetch_text(TRACKER_URLS["street_dealers"])
    soup = BeautifulSoup(html, "html.parser")
    lines = text_lines(soup)

    useful = take_relevant_lines(
        lines,
        ["street dealer", "dealer", "location", "today", "available", "weed", "cocaine", "meth", "lsd"]
    )

    if not useful:
        useful = lines[:10]

    desc = "\n".join(f"• {x}" for x in useful[:10])
    raw = " | ".join(useful[:14])

    return {
        "title": "💊 Уличные дилеры",
        "description": desc or "Открой карту по ссылке ниже.",
        "url": TRACKER_URLS["street_dealers"],
        "raw": raw or "street_dealers",
        "color": 0x2ECC71,
    }


async def parse_stash_house():
    html = await fetch_text(TRACKER_URLS["stash_house"])
    soup = BeautifulSoup(html, "html.parser")
    lines = text_lines(soup)

    useful = take_relevant_lines(lines, ["stash house", "location", "today", "daily", "raid"])

    if not useful:
        useful = lines[:8]

    desc = "\n".join(f"• {x}" for x in useful[:8])
    raw = " | ".join(useful[:10])

    return {
        "title": "🏠 Дом-тайник",
        "description": desc or "Открой карту по ссылке ниже.",
        "url": TRACKER_URLS["stash_house"],
        "raw": raw or "stash_house",
        "color": 0x3498DB,
    }


async def parse_shipwreck():
    html = await fetch_text(TRACKER_URLS["shipwreck"])
    soup = BeautifulSoup(html, "html.parser")
    lines = text_lines(soup)

    useful = take_relevant_lines(lines, ["shipwreck", "location", "today", "daily", "outfit"])

    if not useful:
        useful = lines[:8]

    desc = "\n".join(f"• {x}" for x in useful[:8])
    raw = " | ".join(useful[:10])

    return {
        "title": "🚢 Кораблекрушение",
        "description": desc or "Открой карту по ссылке ниже.",
        "url": TRACKER_URLS["shipwreck"],
        "raw": raw or "shipwreck",
        "color": 0x1ABC9C,
    }


async def parse_hidden_caches():
    html = await fetch_text(TRACKER_URLS["hidden_caches"])
    soup = BeautifulSoup(html, "html.parser")
    lines = text_lines(soup)

    useful = take_relevant_lines(lines, ["hidden cache", "cache", "location", "today", "daily"])

    if not useful:
        useful = lines[:8]

    desc = "\n".join(f"• {x}" for x in useful[:8])
    raw = " | ".join(useful[:10])

    return {
        "title": "🌊 Скрытые тайники",
        "description": desc or "Открой карту по ссылке ниже.",
        "url": TRACKER_URLS["hidden_caches"],
        "raw": raw or "hidden_caches",
        "color": 0x9B59B6,
    }


TRACKER_PARSERS = [
    ("gun_van", parse_gun_van),
    ("street_dealers", parse_street_dealers),
    ("stash_house", parse_stash_house),
    ("shipwreck", parse_shipwreck),
    ("hidden_caches", parse_hidden_caches),
]


def make_embed(title: str, description: str, url: str, color: int):
    embed = discord.Embed(
        title=title,
        description=description[:4000],
        url=url,
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="GTA Online Bot")
    return embed


async def post_startup_message(channel: discord.TextChannel):
    if not SEND_STARTUP_MESSAGE:
        return
    if state.get("started_once"):
        return

    embed = discord.Embed(
        title="✅ Бот запущен",
        description=(
            "Я онлайн и буду автоматически проверять:\n"
            "• новости GTA Online\n"
            "• фургон с оружием\n"
            "• уличных дилеров\n"
            "• дом-тайник\n"
            "• кораблекрушение\n"
            "• скрытые тайники"
        ),
        color=0x57F287,
        timestamp=datetime.now(timezone.utc),
    )
    await channel.send(embed=embed)
    state["started_once"] = True
    save_state(state)


async def check_news(channel: discord.TextChannel):
    try:
        news = await fetch_news_items()
        changed = False
        for item in reversed(news):
            if item["url"] in state["sent_news_links"]:
                continue

            embed = make_embed(
                title=f"📰 {item['title']}",
                description="Новая новость GTA Online.",
                url=item["url"],
                color=0x5865F2,
            )
            await channel.send(embed=embed)
            state["sent_news_links"].append(item["url"])
            changed = True

        if len(state["sent_news_links"]) > 200:
            state["sent_news_links"] = state["sent_news_links"][-200:]

        if changed:
            save_state(state)
    except Exception as e:
        print("NEWS ERROR:", e)


async def check_trackers(channel: discord.TextChannel):
    changed = False
    for key, parser in TRACKER_PARSERS:
        try:
            info = await parser()
            current_hash = hash_text(info["raw"])
            previous_hash = state["tracker_hashes"].get(key)

            if current_hash != previous_hash:
                embed = make_embed(
                    title=info["title"],
                    description=info["description"],
                    url=info["url"],
                    color=info["color"],
                )
                await channel.send(embed=embed)
                state["tracker_hashes"][key] = current_hash
                changed = True
                await asyncio.sleep(2)
        except Exception as e:
            print(f"TRACKER ERROR [{key}]:", e)

    if changed:
        save_state(state)


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
    await ctx.send("Проверяю текущие GTA Online события...")
    await check_news(ctx.channel)
    await check_trackers(ctx.channel)
    await ctx.send("Готово.")


@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    bot.loop.create_task(loop_task())


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

bot.run(TOKEN)
