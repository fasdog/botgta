from __future__ import annotations

import discord


CATEGORY_STYLES = {
    "news": {"title": "📰 GTA News", "color": 0x3498DB},
    "weekly": {"title": "💸 Weekly Update", "color": 0x2ECC71},
    "gunvan": {"title": "🔫 Gun Van", "color": 0xE67E22},
    "dealers": {"title": "💊 Street Dealers", "color": 0x9B59B6},
    "stash": {"title": "🏠 Stash House", "color": 0xF1C40F},
    "shipwreck": {"title": "🚢 Shipwreck", "color": 0x1ABC9C},
    "caches": {"title": "📦 Hidden Caches", "color": 0x95A5A6},
}


def _truncate(text: str, limit: int = 3800) -> str:
    if not text:
        return "Нет данных."
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def make_update_embed(update, updated_at: str) -> discord.Embed:
    style = CATEGORY_STYLES.get(
        update.category,
        {"title": "📢 GTA Update", "color": 0x5865F2},
    )

    embed = discord.Embed(
        title=update.title or style["title"],
        description=_truncate(update.text),
        color=style["color"],
        timestamp=discord.utils.utcnow(),
    )

    source_name = getattr(update, "source_name", "") or "Автоисточник"
    source_url = getattr(update, "source_url", "") or ""
    sources = getattr(update, "sources", []) or []

    if source_url:
        embed.add_field(
            name="Источник",
            value=f"[{source_name}]({source_url})",
            inline=False,
        )
    elif sources:
        embed.add_field(
            name="Источники",
            value="\n".join(f"• {item}" for item in sources[:5]),
            inline=False,
        )
    else:
        embed.add_field(
            name="Источник",
            value=source_name,
            inline=False,
        )

    embed.add_field(
        name="Категория",
        value=update.category,
        inline=True,
    )

    embed.set_footer(text=f"Обновлено: {updated_at}")
    return embed
