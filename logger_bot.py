from dotenv import load_dotenv
import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters import Command
from aiogram.filters import CommandStart

from telegram_logging import setup_telegram_error_logging
from telegram_network import get_telegram_proxy_url
from telegram_subscriptions import add_subscriber_chat_id
from telegram_subscriptions import load_subscriber_chat_ids
from telegram_subscriptions import remove_subscriber_chat_id


load_dotenv()
setup_telegram_error_logging("logger-bot")

BOT_TOKEN = os.getenv("LOGGER_TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("LOGGER_TELEGRAM_BOT_TOKEN не найден")

telegram_proxy_url = get_telegram_proxy_url()
bot_session = AiohttpSession(proxy=telegram_proxy_url) if telegram_proxy_url else None
bot = Bot(token=BOT_TOKEN, session=bot_session)
dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


def actor_label(message: types.Message) -> str:
    username = message.from_user.username if message.from_user else "-"
    return f"chat_id={message.chat.id} type={message.chat.type} username={username}"


@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "Команды:\n"
        "/subscribe - подписаться на ошибки сервисов\n"
        "/unsubscribe - отписаться\n"
        "/status - показать статус подписки"
    )


@dp.message(Command("subscribe"))
async def subscribe(message: types.Message):
    added = add_subscriber_chat_id(str(message.chat.id))
    logger.info("LOGGER SUBSCRIBE %s added=%s", actor_label(message), added)
    if added:
        await message.answer("Подписка включена.")
        return
    await message.answer("Этот чат уже подписан.")


@dp.message(Command("unsubscribe"))
async def unsubscribe(message: types.Message):
    removed = remove_subscriber_chat_id(str(message.chat.id))
    logger.info("LOGGER UNSUBSCRIBE %s removed=%s", actor_label(message), removed)
    if removed:
        await message.answer("Подписка отключена.")
        return
    await message.answer("Этот чат не был подписан.")


@dp.message(Command("status"))
async def status(message: types.Message):
    is_subscribed = str(message.chat.id) in load_subscriber_chat_ids()
    await message.answer(
        f"Статус: {'подписан' if is_subscribed else 'не подписан'}\n"
        f"chat_id: {message.chat.id}"
    )


@dp.message(F.text)
async def fallback(message: types.Message):
    await message.answer("Используй /subscribe, /unsubscribe или /status.")


async def main():
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
