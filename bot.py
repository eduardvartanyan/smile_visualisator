from dotenv import load_dotenv
import os

import asyncio
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart


load_dotenv()

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")

API_URL = "http://91.229.11.38"
API_KEY = os.getenv("BACKEND_API_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer("Отправь фото — я оживлю его 🎬")


@dp.message(lambda message: message.photo)
async def handle_photo(message: types.Message):

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    image_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    await message.answer("Создаю видео... ⏳")

    r = requests.post(
        f"{API_URL}/generate-video",
        headers={
            "X-API-Key": API_KEY
        },
        json={
            "image_url": image_url
        }
    )

    data = r.json()

    task_id = data["yes_task_id"]

    while True:

        await asyncio.sleep(10)

        r = requests.get(
            f"{API_URL}/task/{task_id}",
            headers={
                "X-API-Key": API_KEY
            }
        )

        status = r.json()

        result_url = status.get("result_url")

        if result_url:
            await message.answer_video(result_url)
            break


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())