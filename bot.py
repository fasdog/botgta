
import os
import json
from datetime import datetime, timezone

import discord
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
SEND_STARTUP_MESSAGE = os.getenv("SEND_STARTUP_MESSAGE", "true").lower() == "true"

DATA_FILE = "state.json"

DEFAULT_STATE = {
    "gunvan": {"text": "Нет данных.", "updated_at": ""},
    "dealers": {"text": "Нет данных.", "updated_at": ""},
    "stash": {"text": "Нет данных.", "updated_at": ""},
    "shipwreck": {"text": "Нет данных.", "updated_at": ""},
    "caches": {"text": "Нет данных.", "updated_at": ""},
    "news": {"text": "Нет данных.", "updated_at": ""},
    "weekly": {"text": "Нет данных.", "updated_at": ""},
}

META = {
    "gunvan": {"title": "🚚 Фургон с оружием обновился", "color": 0xF59E0B},
    "dealers": {"title": "💊 Уличные дилеры обновились", "color": 0x22C55E},
    "stash": {"title": "🏠 Дом-тайник обновился", "color": 0x3B82F6},
    "shipwreck": {"title": "🚢 Кораблекрушение обновилось", "color": 0x14B8A6},
    "caches": {"title": "🌊 Скрытые тайники обновились", "color": 0xA855F7},
    "news": {"title": "📰 Новости GTA Online", "color": 0x5865F2},
    "weekly": {"title": "🎯 Бонусы недели GTA Online", "color": 0xEF4444},
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def load_state():
    if not os.path.exists(DATA_FILE):
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE.copy()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = DEFAULT_STATE.copy()
        for k, v in data.items():
            merged[k] = v
        return merged
    except Exception:
        save_state(DEFAULT_STATE)
        return DEFAULT_STATE.copy()


def save_state(state):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


state = load_state()


def make_embed(key: str, text: str):
    meta = META[key]
    embed = discord.Embed(
        title=meta["title"],
        description=text,
        color=meta["color"],
        timestamp=datetime.now(timezone.utc),
    )
    updated = state.get(key, {}).get("updated_at", "")
    if updated:
        embed.set_footer(text=f"Обновлено: {updated}")
    else:
        embed.set_footer(text="GTA Text Alerts Bot")
    return embed


async def post_update(channel, key: str, text: str):
    state[key] = {"text": text, "updated_at": now_text()}
    save_state(state)
    await channel.send(embed=make_embed(key, text))


async def send_current(ctx_or_channel, key: str):
    text = state.get(key, {}).get("text", "Нет данных.")
    await ctx_or_channel.send(embed=make_embed(key, text))


def admin_only():
    async def predicate(ctx):
        return ctx.author.guild_permissions.manage_guild
    return commands.check(predicate)


@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    if SEND_STARTUP_MESSAGE:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="✅ Бот запущен",
                description=(
                    "Я работаю в режиме текстовых оповещений.\n\n"
                    "Команды просмотра:\n"
                    "`!gta` `!gunvan` `!dealers` `!stash` `!shipwreck` `!caches` `!news` `!weekly` `!status`\n\n"
                    "Админ-команды обновления:\n"
                    "`!setgunvan текст`\n"
                    "`!setdealers текст`\n"
                    "`!setstash текст`\n"
                    "`!setshipwreck текст`\n"
                    "`!setcaches текст`\n"
                    "`!setnews текст`\n"
                    "`!setweekly текст`"
                ),
                color=0x22C55E,
                timestamp=datetime.now(timezone.utc),
            )
            await channel.send(embed=embed)


@bot.command()
async def gta(ctx):
    order = ["gunvan", "dealers", "stash", "shipwreck", "caches", "weekly", "news"]
    for key in order:
        await send_current(ctx, key)


@bot.command()
async def gunvan(ctx):
    await send_current(ctx, "gunvan")


@bot.command()
async def dealers(ctx):
    await send_current(ctx, "dealers")


@bot.command()
async def stash(ctx):
    await send_current(ctx, "stash")


@bot.command()
async def shipwreck(ctx):
    await send_current(ctx, "shipwreck")


@bot.command()
async def caches(ctx):
    await send_current(ctx, "caches")


@bot.command()
async def news(ctx):
    await send_current(ctx, "news")


@bot.command()
async def weekly(ctx):
    await send_current(ctx, "weekly")


@bot.command()
async def status(ctx):
    filled = sum(1 for k in state if state[k]["text"] != "Нет данных.")
    embed = discord.Embed(
        title="📊 Статус бота",
        description=(
            "Режим: только текстовые оповещения\n"
            f"Заполненных разделов: {filled}/{len(state)}\n"
            f"Канал: {CHANNEL_ID}"
        ),
        color=0x95A5A6,
        timestamp=datetime.now(timezone.utc),
    )
    await ctx.send(embed=embed)


@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="❓ Команды",
        description=(
            "Просмотр:\n"
            "`!gta` — все текущие оповещения\n"
            "`!gunvan` `!dealers` `!stash` `!shipwreck` `!caches`\n"
            "`!weekly` — бонусы недели\n"
            "`!news` — новости\n"
            "`!status`\n\n"
            "Обновление для админа:\n"
            "`!setgunvan текст`\n"
            "`!setdealers текст`\n"
            "`!setstash текст`\n"
            "`!setshipwreck текст`\n"
            "`!setcaches текст`\n"
            "`!setnews текст`\n"
            "`!setweekly текст`"
        ),
        color=0x7289DA,
    )
    await ctx.send(embed=embed)


@bot.command()
@admin_only()
async def setgunvan(ctx, *, text: str):
    await post_update(ctx.channel, "gunvan", text)


@bot.command()
@admin_only()
async def setdealers(ctx, *, text: str):
    await post_update(ctx.channel, "dealers", text)


@bot.command()
@admin_only()
async def setstash(ctx, *, text: str):
    await post_update(ctx.channel, "stash", text)


@bot.command()
@admin_only()
async def setshipwreck(ctx, *, text: str):
    await post_update(ctx.channel, "shipwreck", text)


@bot.command()
@admin_only()
async def setcaches(ctx, *, text: str):
    await post_update(ctx.channel, "caches", text)


@bot.command()
@admin_only()
async def setnews(ctx, *, text: str):
    await post_update(ctx.channel, "news", text)


@bot.command()
@admin_only()
async def setweekly(ctx, *, text: str):
    await post_update(ctx.channel, "weekly", text)


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

bot.run(TOKEN)
