
import discord
from discord.ext import commands, tasks
import os
from PIL import Image, ImageDraw

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

MAP_SIZE = (800, 800)

def make_map(title, points):
    img = Image.new("RGB", MAP_SIZE, (30,30,30))
    draw = ImageDraw.Draw(img)
    
    for p in points:
        x = int(p[0] * MAP_SIZE[0])
        y = int(p[1] * MAP_SIZE[1])
        draw.ellipse((x-8,y-8,x+8,y+8), fill=(255,80,80))
    
    draw.text((20,20), title, fill=(255,255,255))
    
    path = f"/tmp/{title}.png"
    img.save(path)
    return path

@bot.event
async def on_ready():
    print("BOT READY")
    auto_dashboard.start()

@tasks.loop(minutes=60)
async def auto_dashboard():
    ch = bot.get_channel(CHANNEL_ID)
    if not ch:
        return
    
    embed = discord.Embed(
        title="📊 GTA Online Dashboard",
        description="Актуальные события",
        color=0x00ff99
    )
    
    embed.add_field(name="Gun Van", value="доступен", inline=True)
    embed.add_field(name="Dealers", value="активны", inline=True)
    embed.add_field(name="Stash", value="есть", inline=True)
    
    await ch.send(embed=embed)

@bot.command()
async def gunvan(ctx):
    pts = [(0.3,0.4)]
    img = make_map("GunVan", pts)
    await ctx.send(file=discord.File(img))

@bot.command()
async def dealers(ctx):
    pts = [(0.6,0.5),(0.2,0.7)]
    img = make_map("Dealers", pts)
    await ctx.send(file=discord.File(img))

@bot.command()
async def stash(ctx):
    pts = [(0.5,0.2)]
    img = make_map("Stash", pts)
    await ctx.send(file=discord.File(img))

@bot.command()
async def shipwreck(ctx):
    pts = [(0.8,0.8)]
    img = make_map("Shipwreck", pts)
    await ctx.send(file=discord.File(img))

bot.run(TOKEN)
