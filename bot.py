from dotenv import load_dotenv
import os

import asyncio
import requests
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import CommandStart

from telegram_network import get_telegram_proxy_url
from telegram_logging import setup_telegram_error_logging


load_dotenv()
setup_telegram_error_logging("ai-bot")

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

API_URL = "http://91.229.11.38"
API_KEY = os.getenv("BACKEND_API_TOKEN")

telegram_proxy_url = get_telegram_proxy_url()
bot_session = AiohttpSession(proxy=telegram_proxy_url) if telegram_proxy_url else None
bot = Bot(token=BOT_TOKEN, session=bot_session)
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


def response_preview(response: requests.Response, limit: int = 1000) -> str:
    body = response.text[:limit]
    if len(response.text) > limit:
        body += "...(truncated)"
    return f"status={response.status_code} body={body}"


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Отправь фото — я оживлю его 🎬")

from aiogram import F
@dp.message(F.photo)
async def handle_photo(message: types.Message):
    logger.info("PHOTO HANDLER START user_id=%s", message.from_user.id if message.from_user else "unknown")

    try:
        photo = message.photo[-1]
        logger.info("PHOTO RECEIVED file_id=%s", photo.file_id)

        file = await bot.get_file(photo.file_id)
        logger.info("FILE PATH=%s", file.file_path)

        image_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        logger.info("IMAGE URL=%s", image_url)

        await message.answer("Создаю видео... ⏳")
        logger.info("WAIT MESSAGE SENT")

        r = requests.post(
            f"{API_URL}/generate-video",
            headers={"X-API-Key": API_KEY},
            json={"image_url": image_url},
            timeout=60
        )

        logger.info("BACKEND STATUS=%s", r.status_code)
        logger.info("BACKEND RESPONSE=%s", r.text)
        if r.status_code >= 400:
            logger.error(
                "event=backend_generate_video user_id=%s %s",
                message.from_user.id if message.from_user else "unknown",
                response_preview(r),
            )

        r.raise_for_status()

        data = r.json()
        task_id = data["task_id"]
        logger.info("TASK ID=%s", task_id)

        while True:
            await asyncio.sleep(10)

            r = requests.get(
                f"{API_URL}/task/{task_id}",
                headers={"X-API-Key": API_KEY},
                timeout=60
            )

            logger.info("TASK POLL STATUS=%s", r.status_code)
            logger.info("TASK POLL RESPONSE=%s", r.text)
            if r.status_code >= 400:
                logger.error("event=backend_task_poll task_id=%s %s", task_id, response_preview(r))

            r.raise_for_status()

            status_data = r.json()
            result_url = status_data.get("result")

            if result_url:
                await message.answer_video(result_url)
                logger.info("VIDEO SENT result_url=%s", result_url)
                break

    except Exception as e:
        logger.exception(
            "event=photo_handler_failed user_id=%s",
            message.from_user.id if message.from_user else "unknown",
        )
        await message.answer(f"Ошибка при обработке фото: {e}")


async def main():
    # If a webhook was configured previously, Telegram will reject getUpdates until it is removed.
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
