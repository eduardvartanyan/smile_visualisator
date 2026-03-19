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
curl -X POST 'http://91.229.11.38/generate-video' \
-H 'Content-Type: application/json' \
-H 'X-API-Key: D1d-Gk4-jxC-rhV' \
-d '{"image_url":"https://ipvartanyan.ru/imgs/12.webp"}'
```

```curl
curl 'http://91.229.11.38/task/109444' \
  -H 'X-API-Key: D1d-Gk4-jxC-rhV'
```