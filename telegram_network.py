import os
from urllib.parse import urlparse


TELEGRAM_HOSTS = {
    "api.telegram.org",
}


def get_telegram_proxy_url() -> str | None:
    return (
        os.getenv("TELEGRAM_PROXY_URL")
        or os.getenv("TG_PROXY_URL")
        or os.getenv("HTTPS_PROXY")
        or os.getenv("https_proxy")
    )


def get_requests_proxies_for_url(url: str) -> dict[str, str] | None:
    proxy_url = get_telegram_proxy_url()
    if not proxy_url:
        return None

    hostname = urlparse(url).hostname
    if hostname not in TELEGRAM_HOSTS:
        return None

    return {
        "http": proxy_url,
        "https": proxy_url,
    }


def is_telegram_url(url: str) -> bool:
    return urlparse(url).hostname in TELEGRAM_HOSTS
