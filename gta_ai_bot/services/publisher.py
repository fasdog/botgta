from __future__ import annotations

import re


CATEGORY_LABELS = {
    "news": "📰 Новости GTA Online",
    "weekly": "💸 Еженедельное обновление",
    "gunvan": "🔫 Gun Van",
    "dealers": "💊 Street Dealers",
    "stash": "🏠 Stash House",
    "shipwreck": "🚢 Shipwreck",
    "caches": "📦 Caches",
}


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _smart_trim(text: str, limit: int = 1800) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text

    cut = text[:limit]
    last_break = max(cut.rfind("\n\n"), cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if last_break > 400:
        cut = cut[:last_break].rstrip()

    return cut.rstrip() + "…"


def _looks_like_heading(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    return (
        len(line) <= 110
        and (
            line.isupper()
            or line.endswith(":")
            or ("GTA $" in line and len(line) <= 120)
        )
    )


def _split_paragraphs(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").strip()
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if parts:
        return parts

    lines = [_clean_line(x) for x in text.split("\n") if _clean_line(x)]
    return lines


def _format_body(text: str) -> str:
    parts = _split_paragraphs(text)
    if not parts:
        return "Нет данных."

    out: list[str] = []
    normal_count = 0

    for part in parts:
        if _looks_like_heading(part):
            out.append(f"**{part}**")
            continue

        if part.startswith(("• ", "- ", "— ")):
            out.append(part)
            continue

        out.append(part)
        normal_count += 1

        if normal_count >= 5:
            break

    return _smart_trim("\n\n".join(out), 1800)


def make_update_message(update, updated_at: str) -> str:
    label = CATEGORY_LABELS.get(update.category, "📢 Обновление")
    title = (getattr(update, "title", "") or "Без названия").strip()
    text = _format_body(getattr(update, "text", "") or "")
    source_name = (getattr(update, "source_name", "") or "Источник").strip()
    source_url = (getattr(update, "source_url", "") or "").strip()

    lines = [
        f"{label}",
        "",
        f"**{title}**",
        "",
        text,
    ]

    if source_url:
        lines.extend(
            [
                "",
                f"🔗 Источник: {source_name}",
                source_url,
            ]
        )

    lines.extend(
        [
            "",
            f"_Обновлено: {updated_at}_",
        ]
    )

    return "\n".join(lines)
