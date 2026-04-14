Перезапустить приложение:
```bash
sudo systemctl restart ai-backend
sudo systemctl status ai-backend
```

Перезапустить ТГ-бот:
```bash
sudo systemctl restart ai-bot
sudo systemctl status ai-bot
```

Перезапустить бот логирования:
```bash
sudo systemctl restart logger-bot
sudo systemctl status logger-bot
```

Установка зависимостей:
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Переменные окружения для Telegram:
```bash
TG_BOT_TOKEN=...
BACKEND_API_TOKEN=...
TELEGRAM_PROXY_URL=socks5://login:password@proxy-host:1080
LOGGER_TELEGRAM_BOT_TOKEN=...
LOGGER_TELEGRAM_SUBSCRIBERS_FILE=/home/ai-backend/logger_subscribers.json
```

Если для `aiogram` используется `socks5://...`, на сервере может понадобиться поддержка SOCKS для `aiohttp`.
Самый беспроблемный вариант для старта: обычный `http://` или `https://` proxy URL.

Что изменено по схеме работы:
```text
- бот запускается через long polling (aiogram start_polling)
- перед стартом polling бот удаляет старый webhook у Telegram
- запросы к Telegram Bot API и скачивание telegram file URL можно гнать через TELEGRAM_PROXY_URL
- logger-bot обрабатывает /subscribe, /unsubscribe и /status; ошибки уходят только подписчикам
```

Эндпоинты:
```curl
curl -X POST 'https://smile.stomadmin.com/generate-video' \
-H 'Content-Type: application/json' \
-H 'X-API-Key: D1d-Gk4-jxC-rhV' \
-d '{"image_url":"https://ipvartanyan.ru/imgs/12.webp"}'
```

```curl
curl 'https://smile.stomadmin.com/task/109444' \
  -H 'X-API-Key: D1d-Gk4-jxC-rhV'
```

Логи:
```bash
# Слежение за всеми логами (не только ошибки)
sudo journalctl -u ai-backend -f

# Или просмотр последних логов
sudo journalctl -u ai-backend -n 50 --no-pager

# Только ошибки
sudo journalctl -u ai-backend -p err -b
```
