from __future__ import annotations

import asyncio
import logging

import aiohttp
import discord
from discord.ext import commands, tasks

from .collectors.webpage import ConfiguredWebCollector
from .config import Settings
from .models import CATEGORY_ORDER, META, now_text
from .services.aggregator import GTAAIAggregator
from .services.publisher import make_update_message
from .storage import StateStore

log = logging.getLogger("gta_ai_bot")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


class GTANewsBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        super().__init__(command_prefix="!", intents=intents, help_command=None)

        self.settings = settings
        self.store = StateStore(settings.state_file)
        self.state = self.store.load()
        self.http_session: aiohttp.ClientSession | None = None
        self.aggregator: GTAAIAggregator | None = None
        self.scan_lock = asyncio.Lock()

    async def setup_hook(self) -> None:
        timeout = aiohttp.ClientTimeout(total=self.settings.request_timeout_seconds)
        self.http_session = aiohttp.ClientSession(
            timeout=timeout,
            headers={"User-Agent": "gta-news-bot/3.2"},
        )
        self.aggregator = GTAAIAggregator(self.settings.max_source_text_chars)
        self.poll_sources.change_interval(minutes=max(1, self.settings.poll_minutes))
        self.poll_sources.start()

    async def close(self) -> None:
        if self.http_session:
            await self.http_session.close()
        await super().close()

    async def resolve_target_channel(self) -> discord.abc.Messageable | None:
        if not self.settings.channel_id:
            log.warning("CHANNEL_ID is not set")
            return None

        channel = self.get_channel(self.settings.channel_id)
        if channel is not None:
            return channel

        try:
            return await self.fetch_channel(self.settings.channel_id)
        except Exception:
            log.exception("Failed to fetch target channel %s", self.settings.channel_id)
            return None

    async def on_ready(self):
        log.info("Bot logged in as %s", self.user)

        channel = await self.resolve_target_channel()
        if channel is None:
            log.warning("Target channel %s not found", self.settings.channel_id)
        elif self.settings.send_startup_message:
            embed = discord.Embed(
                title="🤖 GTA News Bot запущен",
                description=(
                    "Я онлайн.\n"
                    "Режим: полностью бесплатный, без OpenAI.\n"
                    "Бот сам читает источники и публикует обновления.\n\n"
                    "**Команды просмотра:**\n"
                    "`!gta` `!news` `!weekly`"
                ),
                color=0x2ECC71,
                timestamp=discord.utils.utcnow(),
            )
            try:
                await channel.send(embed=embed)
            except Exception:
                log.exception("Failed to send startup message to channel %s", self.settings.channel_id)

        if self.settings.scan_on_startup:
            try:
                await self.run_scan(reason="startup")
            except Exception:
                log.exception("Startup scan failed")

    async def collect_items(self):
        assert self.http_session is not None

        log.info("Configured sources: %s", len(self.settings.sources))

        collectors = []
        for source in self.settings.sources:
            try:
                log.info("Initializing collector for source: %s", source.get("name", source))
                collectors.append(ConfiguredWebCollector(self.http_session, source))
            except Exception:
                log.exception("Failed to initialize collector for source=%s", source)

        items = []
        for collector in collectors:
            try:
                collected = await collector.collect()
                log.info(
                    "Collector %s returned %s items",
                    collector.__class__.__name__,
                    len(collected),
                )
                items.extend(collected)
            except Exception:
                log.exception("Collector failed: %s", collector.__class__.__name__)

        log.info("Total collected items: %s", len(items))
        return items[: self.settings.max_sources_per_cycle]

    async def run_scan(self, reason: str = "scheduled") -> int:
        async with self.scan_lock:
            channel = await self.resolve_target_channel()
            if channel is None:
                log.warning("Target channel %s not found", self.settings.channel_id)
                return 0

            items = await self.collect_items()
            if not items:
                log.info("No items collected on %s scan", reason)
                return 0

            assert self.aggregator is not None

            try:
                updates = await self.aggregator.summarize(items)
            except Exception:
                log.exception("Aggregator failed on %s scan", reason)
                return 0

            published = 0
            for update in updates:
                previous_hash = self.state.get(update.category, {}).get("hash", "")
                if previous_hash == update.dedupe_key:
                    continue

                updated_at = now_text()
                payload = update.to_storage_dict()
                payload["updated_at"] = updated_at
                self.state[update.category] = payload
                self.store.save(self.state)

                try:
                    await channel.send(make_update_message(update, updated_at))
                    published += 1
                except Exception:
                    log.exception("Failed to publish update for category=%s", update.category)

            log.info("Scan reason=%s collected=%s published=%s", reason, len(items), published)
            return published

    @tasks.loop(minutes=20)
    async def poll_sources(self):
        await self.run_scan(reason="scheduled")

    @poll_sources.before_loop
    async def before_poll_sources(self):
        await self.wait_until_ready()


settings = Settings.from_env()
bot = GTANewsBot(settings)


def make_state_embed(key: str):
    meta = META[key]
    entry = bot.state.get(key, {})

    embed = discord.Embed(
        title=meta["title"],
        description=entry.get("text", "Нет данных."),
        color=meta["color"],
        timestamp=discord.utils.utcnow(),
    )

    sources = entry.get("sources", [])
    if sources:
        embed.add_field(name="Источники", value="\n".join(sources[:5]), inline=False)

    updated = entry.get("updated_at", "")
    embed.set_footer(text=f"Обновлено: {updated or 'никогда'}")
    return embed


async def send_current(ctx_or_channel, key: str):
    await ctx_or_channel.send(embed=make_state_embed(key))


@bot.command()
async def gta(ctx):
    for key in CATEGORY_ORDER:
        await send_current(ctx, key)


@bot.command()
async def news(ctx):
    await send_current(ctx, "news")


@bot.command()
async def weekly(ctx):
    await send_current(ctx, "weekly")


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


@bot.command(name="help")
async def help_command(ctx):
    embed = discord.Embed(
        title="❓ Команды",
        description=(
            "`!gta` — все текущие обновления\n"
            "`!news` `!weekly`\n\n"
            "Бот работает без OpenAI."
        ),
        color=0x7289DA,
        timestamp=discord.utils.utcnow(),
    )
    await ctx.send(embed=embed)


if not settings.discord_token:
    raise RuntimeError("DISCORD_TOKEN is not set")

bot.run(settings.discord_token)
