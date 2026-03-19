from __future__ import annotations

from datetime import datetime, timezone

import discord

from ..models import AIUpdate, META


def make_update_embed(update: AIUpdate, updated_at: str) -> discord.Embed:
    meta = META[update.category]
    source_block = "\n".join(f"• {name}" for name in update.source_names[:5]) or "• Автоагрегация"
    embed = discord.Embed(
        title=f"{meta['title']} — {update.title}",
        description=update.summary,
        color=meta["color"],
        timestamp=datetime.now(timezone.utc),
    )
    if update.facts:
        embed.add_field(name="Факты", value="\n".join(f"• {fact}" for fact in update.facts[:6]), inline=False)
    if update.source_urls:
        embed.add_field(
            name="Источники",
            value="\n".join(update.source_urls[:5]),
            inline=False,
        )
    embed.add_field(name="Собрано из", value=source_block[:1024], inline=False)
    embed.set_footer(text=f"Автообновление ИИ • {updated_at} • confidence={update.confidence:.2f}")
    return embed
