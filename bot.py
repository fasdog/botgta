
import os
import asyncio
import aiohttp
import discord
from discord.ext import commands
from bs4 import BeautifulSoup

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

sent_links = set()

async def fetch_news():
    url = "https://www.rockstargames.com/newswire"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as r:
            html = await r.text()

    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = a["href"]

        if not title or "gta" not in title.lower():
            continue

        link = href if href.startswith("http") else f"https://www.rockstargames.com{href}"
        posts.append((title, link))

    return posts[:5]

async def news_loop():
    await bot.wait_until_ready()
    channel = bot.get_channel(CHANNEL_ID)

    while not bot.is_closed():
        try:
            news = await fetch_news()

            for title, link in news:
                if link in sent_links:
                    continue

                embed = discord.Embed(
                    title=title,
                    url=link,
                    description="📰 Новая новость GTA Online",
                    color=0x00ff99
                )

                await channel.send(embed=embed)
                sent_links.add(link)

            await asyncio.sleep(CHECK_INTERVAL * 60)

        except Exception as e:
            print("ERROR:", e)
            await asyncio.sleep(60)

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    bot.loop.create_task(news_loop())

bot.run(TOKEN)
