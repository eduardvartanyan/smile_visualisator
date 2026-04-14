import logging
import os
import socket
import threading
from typing import Optional

import requests
from urllib3.util import connection as urllib3_connection

from telegram_network import get_requests_proxies_for_url
from telegram_subscriptions import load_subscriber_chat_ids


class TelegramErrorHandler(logging.Handler):
    _ipv4_lock = threading.Lock()

    def __init__(self, bot_token: str, service_name: str, timeout: int = 10):
        super().__init__(level=logging.ERROR)
        self.bot_token = bot_token
        self.service_name = service_name
        self.timeout = timeout
        self.hostname = socket.gethostname()
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.session = requests.Session()
        proxies = get_requests_proxies_for_url(self.api_url)
        if proxies:
            self.session.proxies.update(proxies)

    def _post(self, payload: dict) -> None:
        # On hosts with broken IPv6 routing, force Telegram requests over IPv4.
        with self._ipv4_lock:
            original_allowed_gai_family = urllib3_connection.allowed_gai_family
            urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
            try:
                response = self.session.post(
                    self.api_url,
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
            finally:
                urllib3_connection.allowed_gai_family = original_allowed_gai_family

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self._format_record(record)
            text = (
                f"{self.service_name} | {record.levelname} | {self.hostname}\n\n"
                f"{message}"
            )

            for chat_id in self.chat_ids():
                self._post(
                    {
                        "chat_id": chat_id,
                        "text": text[:4000],
                    }
                )
        except Exception:
            self.handleError(record)

    @staticmethod
    def _format_record(record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            formatter = logging.Formatter()
            exc_text = formatter.formatException(record.exc_info)
            return f"{message}\n{exc_text}"
        return message

    def chat_ids(self) -> list[str]:
        return load_subscriber_chat_ids()


def setup_telegram_error_logging(service_name: str) -> Optional[TelegramErrorHandler]:
    bot_token = os.getenv("LOGGER_TELEGRAM_BOT_TOKEN")

    if not bot_token:
        return None

    if not load_subscriber_chat_ids():
        return None

    root_logger = logging.getLogger()
    already_configured = next(
        (
            handler for handler in root_logger.handlers
            if isinstance(handler, TelegramErrorHandler) and handler.service_name == service_name
        ),
        None,
    )
    if already_configured:
        return already_configured

    telegram_handler = TelegramErrorHandler(
        bot_token=bot_token,
        service_name=service_name,
    )
    telegram_handler.setLevel(logging.ERROR)
    telegram_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(telegram_handler)
    return telegram_handler
