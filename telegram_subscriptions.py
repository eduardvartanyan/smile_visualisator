import json
import os
from pathlib import Path


def subscriptions_file_path() -> Path:
    configured_path = os.getenv("LOGGER_TELEGRAM_SUBSCRIBERS_FILE")
    if configured_path:
        return Path(configured_path)
    return Path(__file__).resolve().parent / "logger_subscribers.json"


def load_subscriber_chat_ids() -> list[str]:
    path = subscriptions_file_path()
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    return [str(chat_id) for chat_id in data.get("chat_ids", [])]


def save_subscriber_chat_ids(chat_ids: list[str]) -> None:
    path = subscriptions_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    normalized_chat_ids = sorted({str(chat_id) for chat_id in chat_ids})
    with open(path, "w", encoding="utf-8") as file:
        json.dump({"chat_ids": normalized_chat_ids}, file, ensure_ascii=False, indent=2)


def add_subscriber_chat_id(chat_id: str) -> bool:
    normalized_chat_id = str(chat_id)
    chat_ids = load_subscriber_chat_ids()
    if normalized_chat_id in chat_ids:
        return False

    chat_ids.append(normalized_chat_id)
    save_subscriber_chat_ids(chat_ids)
    return True


def remove_subscriber_chat_id(chat_id: str) -> bool:
    normalized_chat_id = str(chat_id)
    chat_ids = load_subscriber_chat_ids()
    if normalized_chat_id not in chat_ids:
        return False

    save_subscriber_chat_ids([item for item in chat_ids if item != normalized_chat_id])
    return True
