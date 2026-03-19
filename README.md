# GTA Discord Bot Ultra

Ультра-версия Discord-бота для GTA Online.

## Что умеет
- стартовое сообщение при запуске
- авто-проверка новостей GTA Online
- авто-проверка:
  - Gun Van
  - Street Dealers
  - Stash House
  - Shipwreck
  - Hidden Caches
- команда `!gta`
- команды:
  - `!gunvan`
  - `!dealers`
  - `!stash`
  - `!shipwreck`
  - `!caches`
  - `!status`
  - `!help`
- антидубли между перезапусками
- кнопки со ссылками
- опциональный пинг роли
- опциональный перевод заголовков новостей через DeepL

## Railway Variables
Обязательные:
- `DISCORD_TOKEN`
- `CHANNEL_ID`

Необязательные:
- `CHECK_INTERVAL_MINUTES=30`
- `SEND_STARTUP_MESSAGE=true`
- `ROLE_PING_ID=`
- `DEEPL_API_KEY=`

## Примечание
Трекеры парсятся со страниц GTALens. Если у них поменяется вёрстка, может понадобиться обновить парсер.
