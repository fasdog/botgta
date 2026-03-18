# GTA Online News Discord Bot (RU)

Готовый Discord-бот для Railway. Он проверяет Rockstar Games Newswire, находит новые новости по GTA Online и публикует их в канал Discord. Если задан `DEEPL_API_KEY`, бот переводит заголовок и описание на русский.

## Что нужно

- Discord bot token
- ID канала Discord
- Railway + GitHub
- Опционально: ключ DeepL API для автоперевода на русский

## Файлы проекта

- `bot.py` — основной код бота
- `requirements.txt` — зависимости Python
- `Procfile` — команда запуска для Railway
- `.env.example` — пример переменных окружения

## Переменные Railway

Добавь в Railway → Project → Variables:

- `DISCORD_TOKEN` — токен бота Discord
- `CHANNEL_ID` — ID канала, куда отправлять новости
- `DEEPL_API_KEY` — ключ DeepL API, если нужен перевод на русский
- `CHECK_INTERVAL_MINUTES` — интервал проверки, например `30`
- `POST_ON_STARTUP` — `false`, чтобы бот не публиковал старые новости после первого запуска
- `MAX_ARTICLES_TO_SCAN` — сколько свежих статей смотреть за одну проверку
- `HTTP_TIMEOUT_SECONDS` — таймаут HTTP-запросов

## Как загрузить на GitHub

1. Распакуй архив.
2. Создай новый репозиторий на GitHub.
3. Загрузи все файлы из архива в репозиторий.
4. В Railway выбери **Deploy from GitHub Repo**.
5. Добавь переменные окружения.
6. После деплоя открой Logs и проверь, что бот вошёл в Discord.

## Как получить ID канала

В Discord включи Developer Mode → нажми правой кнопкой по каналу → Copy Channel ID.

## Важно

Без `DEEPL_API_KEY` бот будет публиковать оригинальный английский текст. С ключом DeepL будет переводить заголовок и описание на русский.

## Локальный запуск

```bash
pip install -r requirements.txt
python bot.py
```
