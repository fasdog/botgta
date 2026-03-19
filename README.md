# GTA AI Bot v2 — prefilled sources build

Это версия архива, где `SOURCES_JSON` уже заполнен реальными GTA Online-источниками.

## Что внутри
- убраны все ручные админ-команды `!set...`
- бот сам собирает данные по расписанию
- Rockstar Newswire RSS используется как официальный источник новостей и weekly-постов
- GTALens используется как источник по текущим ежедневным и сменяемым активностям
- сводка и классификация делаются через OpenAI

## Источники по умолчанию
Официальные новости:
- `https://www.rockstargames.com/newswire/rss`

Карты и ежедневные активности:
- Gun Van — `https://gtalens.com/map/gun-vans`
- Street Dealers — `https://gtalens.com/map/street-dealers`
- Stash Houses — `https://gtalens.com/map/stash-houses`
- Shipwrecks — `https://gtalens.com/map/ship-wrecks`
- Hidden Caches — `https://gtalens.com/map/hidden-caches`
- Buried Stashes — `https://gtalens.com/map/buried-stashes`
- Treasure Chests — `https://gtalens.com/map/cayo-treasure-chests`

## Файлы конфигурации
- `.env.example` — уже содержит готовый `SOURCES_JSON` в одну строку
- `sources.real.json` — тот же список, но в читаемом формате

## Как работает
1. Бот читает Rockstar Newswire RSS.
2. Бот читает GTALens-страницы целиком (`body`), чтобы LLM увидела активные точки, цены и пометки вида `[active]`.
3. OpenAI классифицирует данные по категориям:
   - `weekly`
   - `news`
   - `gunvan`
   - `dealers`
   - `stash`
   - `shipwreck`
   - `caches`
4. Бот публикует только изменения по новому hash.

## Запуск
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m gta_ai_bot.bot
```

## Практические замечания
- GTALens и Rockstar могут менять верстку. Если текст на какой-то странице перестанет читаться, достаточно заменить URL или селекторы в `SOURCES_JSON`.
- Сейчас GTALens-страницы читаются максимально устойчиво: бот забирает весь текст страницы через `text_selector: "body"`, а разбор уже делает LLM.
- Для Railway/Render удобнее использовать значение `SOURCES_JSON` из `.env.example` или из `sources.real.json`, но в одной строке.
