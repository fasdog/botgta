# GTA Discord Bot Power

Более мощная версия бота для Discord.

## Что умеет
- пишет стартовое сообщение при запуске
- проверяет новости GTA Online
- проверяет:
  - Gun Van
  - Street Dealers
  - Stash House
  - Shipwreck
  - Hidden Caches
- команда `!gta` для ручной проверки

## Railway Variables
- `DISCORD_TOKEN`
- `CHANNEL_ID`
- `CHECK_INTERVAL_MINUTES=30`
- `SEND_STARTUP_MESSAGE=true`

## Важно
Парсинг трекеров сделан по страницам GTALens. Если сайт изменит вёрстку, может понадобиться правка селекторов.
