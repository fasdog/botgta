
import os
import json
from io import BytesIO
from datetime import datetime, timezone

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
SEND_STARTUP_MESSAGE = os.getenv("SEND_STARTUP_MESSAGE", "true").lower() == "true"

DATA_FILE = "locations.json"

DEFAULT_DATA = {
    "gunvan": {"points": [[62, 58]], "label": "Gun Van"},
    "dealers": {"points": [[26, 38], [51, 63], [74, 31]], "label": "Street Dealers"},
    "stash": {"points": [[44, 47]], "label": "Stash House"},
    "shipwreck": {"points": [[86, 70]], "label": "Shipwreck"},
    "caches": {"points": [[18, 77], [34, 82], [70, 76]], "label": "Hidden Caches"},
}

TITLES = {
    "gunvan": "🔫 Фургон с оружием",
    "dealers": "💊 Уличные дилеры",
    "stash": "🏠 Дом-тайник",
    "shipwreck": "🚢 Кораблекрушение",
    "caches": "🌊 Скрытые тайники",
}

COLORS = {
    "gunvan": (255, 184, 0),
    "dealers": (34, 197, 94),
    "stash": (59, 130, 246),
    "shipwreck": (20, 184, 166),
    "caches": (168, 85, 247),
}

ORDER = ["gunvan", "dealers", "stash", "shipwreck", "caches"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA.copy()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


data_store = load_data()


def font(size=22):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def font_regular(size=18):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def parse_point_pair(x, y):
    return [max(0, min(100, float(x))), max(0, min(100, float(y)))]


def draw_pin(draw, x, y, color):
    r = 8
    draw.ellipse((x-r, y-r-6, x+r, y+r-6), fill=color, outline=(255, 255, 255), width=2)
    draw.polygon([(x, y+10), (x-7, y-1), (x+7, y-1)], fill=color, outline=(255, 255, 255))
    draw.ellipse((x-3, y-11, x+3, y-5), fill=(255, 255, 255))


def map_xy(px, py, map_box):
    left, top, right, bottom = map_box
    return int(left + (px / 100.0) * (right - left)), int(top + (py / 100.0) * (bottom - top))


def draw_stylized_map(draw, box):
    left, top, right, bottom = box
    draw.rounded_rectangle(box, radius=18, fill=(23, 79, 138), outline=(86, 131, 184), width=2)

    land = [
        (left+25, top+35), (left+95, top+12), (left+170, top+18), (left+220, top+52),
        (left+248, top+90), (left+252, top+132), (left+228, top+170), (left+193, top+195),
        (left+155, top+206), (left+110, top+198), (left+80, top+210), (left+46, top+194),
        (left+26, top+160), (left+18, top+118), (left+22, top+75)
    ]
    draw.polygon(land, fill=(76, 128, 79))
    draw.line(land + [land[0]], fill=(220, 208, 154), width=3)

    # roads
    for x in range(left+35, right-20, 38):
        draw.line((x, top+28, x, bottom-22), fill=(206, 182, 116), width=1)
    for y in range(top+30, bottom-18, 32):
        draw.line((left+28, y, right-26, y), fill=(206, 182, 116), width=1)

    draw.line((left+48, bottom-42, right-36, top+80), fill=(234, 141, 74), width=4)
    draw.line((left+70, top+40, right-60, bottom-30), fill=(234, 141, 74), width=4)

    draw.text((left+88, top+130), "Los Santos", font=font_regular(16), fill=(255, 255, 255))
    draw.text((left+155, top+28), "Blaine", font=font_regular(14), fill=(245, 245, 245))


def create_dashboard_image():
    W, H = 1600, 1120
    img = Image.new("RGB", (W, H), (10, 14, 22))
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((20, 20, W-20, H-20), radius=28, fill=(18, 24, 36), outline=(56, 74, 100), width=2)
    draw.text((48, 38), "GTA Online Service Dashboard", font=font(34), fill=(255, 255, 255))
    draw.text((50, 84), "Все карты в одном сообщении", font=font_regular(20), fill=(190, 205, 220))

    boxes = [
        (40, 130, 760, 470),
        (800, 130, 1520, 470),
        (40, 510, 760, 850),
        (800, 510, 1520, 850),
        (420, 860, 1140, 1080),
    ]

    for kind, box in zip(ORDER, boxes):
        x1, y1, x2, y2 = box
        draw.rounded_rectangle(box, radius=24, fill=(24, 32, 46), outline=(68, 86, 112), width=2)
        color = COLORS[kind]
        draw.rounded_rectangle((x1+16, y1+16, x1+24, y1+56), radius=4, fill=color)
        draw.text((x1+36, y1+18), TITLES[kind], font=font(24), fill=(255, 255, 255))

        map_box = (x1+24, y1+70, x2-24, y2-22)
        draw_stylized_map(draw, map_box)

        pts = data_store[kind]["points"]
        for idx, (px, py) in enumerate(pts, start=1):
            mx, my = map_xy(px, py, map_box)
            draw_pin(draw, mx, my, color)
            draw.rounded_rectangle((mx+10, my-28, mx+46, my-6), radius=8, fill=(12, 18, 28), outline=color, width=2)
            draw.text((mx+22, my-27), str(idx), font=font_regular(14), fill=(255, 255, 255))

    draw.text((44, 1084), "Админ: !setgunvan / !setdealers / !setstash / !setshipwreck / !setcaches", font=font_regular(16), fill=(175, 190, 205))

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def send_dashboard(channel):
    image = create_dashboard_image()
    file = discord.File(image, filename="gta_dashboard.png")
    embed = discord.Embed(
        title="🗺️ GTA Online — все карты",
        description="Все метки собраны в одном изображении.",
        color=0x3B82F6,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_image(url="attachment://gta_dashboard.png")
    await channel.send(embed=embed, file=file)


@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    if SEND_STARTUP_MESSAGE:
        ch = bot.get_channel(CHANNEL_ID)
        if ch:
            await ch.send("✅ Бот запущен. Команда `!gta` отправляет все карты в одном сообщении.")


@bot.command()
async def gta(ctx):
    await send_dashboard(ctx.channel)


@bot.command()
async def gunvan(ctx):
    await send_dashboard(ctx.channel)


@bot.command()
async def dealers(ctx):
    await send_dashboard(ctx.channel)


@bot.command()
async def stash(ctx):
    await send_dashboard(ctx.channel)


@bot.command()
async def shipwreck(ctx):
    await send_dashboard(ctx.channel)


@bot.command()
async def caches(ctx):
    await send_dashboard(ctx.channel)


@bot.command()
async def status(ctx):
    embed = discord.Embed(
        title="📊 Статус бота",
        description="• Режим: одна картинка со всеми картами\n• Версия: ONE MESSAGE PRO",
        color=0x95A5A6,
        timestamp=datetime.now(timezone.utc),
    )
    await ctx.send(embed=embed)


def admin_only():
    async def predicate(ctx):
        return ctx.author.guild_permissions.manage_guild
    return commands.check(predicate)


@bot.command()
@admin_only()
async def setgunvan(ctx, x: float, y: float):
    data_store["gunvan"]["points"] = [parse_point_pair(x, y)]
    save_data(data_store)
    await ctx.send("✅ Gun Van обновлён.")
    await send_dashboard(ctx.channel)


@bot.command()
@admin_only()
async def setstash(ctx, x: float, y: float):
    data_store["stash"]["points"] = [parse_point_pair(x, y)]
    save_data(data_store)
    await ctx.send("✅ Дом-тайник обновлён.")
    await send_dashboard(ctx.channel)


@bot.command()
@admin_only()
async def setshipwreck(ctx, x: float, y: float):
    data_store["shipwreck"]["points"] = [parse_point_pair(x, y)]
    save_data(data_store)
    await ctx.send("✅ Shipwreck обновлён.")
    await send_dashboard(ctx.channel)


@bot.command()
@admin_only()
async def setdealers(ctx, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float):
    data_store["dealers"]["points"] = [parse_point_pair(x1, y1), parse_point_pair(x2, y2), parse_point_pair(x3, y3)]
    save_data(data_store)
    await ctx.send("✅ Дилеры обновлены.")
    await send_dashboard(ctx.channel)


@bot.command()
@admin_only()
async def setcaches(ctx, x1: float, y1: float, x2: float, y2: float, x3: float, y3: float):
    data_store["caches"]["points"] = [parse_point_pair(x1, y1), parse_point_pair(x2, y2), parse_point_pair(x3, y3)]
    save_data(data_store)
    await ctx.send("✅ Hidden caches обновлены.")
    await send_dashboard(ctx.channel)


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

bot.run(TOKEN)
