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