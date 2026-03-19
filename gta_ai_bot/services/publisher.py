from __future__ import annotations

import discord


CATEGORY_STYLES = {
    "news": {"prefix": "📰", "color": 0x3498DB, "label": "Новости"},
    "weekly": {"prefix": "💸", "color": 0x2ECC71, "label": "Еженедельное обновление"},
    "gunvan": {"prefix": "🔫", "color": 0xE67E22, "label": "Gun Van"},
    "dealers": {"prefix": "💊", "color": 0x9B59B6, "label": "Dealers"},
    "stash": {"prefix": "🏠", "color": 0xF1C40F, "label": "Stash House"},
    "shipwreck": {"prefix": "🚢", "color": 0x1ABC9C, "label": "Shipwreck"},
    "caches": {"prefix": "📦", "color": 0x95A5A6, "label": "Caches"},
}


def _smart_trim(text: str, limit: int = 3500) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text

    cut = text[:limit]
    last_break = max(cut.rfind("\n\n"), cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if last_break > 500:
        cut = cut[:last_break].rstrip()

    return cut.rstrip() + "…"


def _format_text(text: str) -> str:
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not parts:
        return "Нет данных."

    formatted: list[str] = []
    for i, part in enumerate(parts):
        is_heading = (
            len(part) <= 100 and
            (part.isupper() or part.endswith(":") or ("GTA $" in part and len(part) <= 120))
        )

        if is_heading:
            formatted.append(f"**{part}**")
        else:
            formatted.append(part)

        if i >= 4:
            break

    return _smart_trim("\n\n".join(formatted), 3500)


def make_update_embed(update, updated_at: str) -> discord.Embed:
    style = CATEGORY_STYLES.get(
        update.category,
        {"prefix": "📢", "color": 0x5865F2, "label": "Обновление"},
    )

    title = f"{style['prefix']} {update.title or style['label']}"
    text = _format_text(getattr(update, "text", "") or "")

    embed = discord.Embed(
        title=title,
        description=text,
        color=style["color"],
        timestamp=discord.utils.utcnow(),
    )

    source_name = getattr(update, "source_name", "") or "Источник"
    source_url = getattr(update, "source_url", "") or ""

    if source_url:
        embed.add_field(
            name="Источник",
            value=f"[{source_name}]({source_url})",
            inline=False,
        )

    embed.set_footer(text=f"Обновлено: {updated_at}")
    return embed
