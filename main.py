from dotenv import load_dotenv
import os
import sys
import time
from pathlib import Path

import requests
import replicate


# =========================
# Конфиг
# =========================

load_dotenv()

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
YES_API_TOKEN = os.getenv("YES_API_TOKEN")

if not REPLICATE_API_TOKEN:
    raise RuntimeError("REPLICATE_API_TOKEN не найден. Проверьте .env")

if not YES_API_TOKEN:
    raise RuntimeError("YES_API_TOKEN не найден. Проверьте .env")

OUTPUT_DIR = Path("output-images")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_IMAGE_URL = "https://ipvartanyan.ru/imgs/13.jpg"

FLUX_PROMPT = (
    "perfect white teeth, Hollywood smile, smooth nasolabial folds, "
    "youthful face skin, natural skin texture, professional portrait retouching, realistic lighting"
)

ANIMATE_PROMPT = (
    "The person looks into the camera, smiles wide showing beautiful white teeth, "
    "turns head slightly and nods, realistic skin texture"
)

YES_CREATE_URL = "https://api.yesai.su/v2/yesvideo/aniimage/kling"
YES_STATUS_URL_TEMPLATE = "https://api.yesai.su/v2/yesvideo/animations/{task_id}"

YES_CUSTOMER_ID = "ncsehpgt"
YES_VERSION = "2.5"
YES_DURATION = "5"
YES_DIMENSIONS = "16:9"

POLL_INTERVAL_SEC = 5
POLL_TIMEOUT_SEC = 60 * 5  # 5 минут


# =========================
# Утилиты
# =========================

def download_file(url: str, dest_path: Path) -> None:
    response = requests.get(url, timeout=60, stream=True)
    response.raise_for_status()

    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


def spinner_message(message: str, step: int) -> str:
    frames = ["|", "/", "-", "\\"]
    return f"\r{message} {frames[step % len(frames)]}"


# =========================
# Шаг 1. Генерация / редактирование картинки через Replicate
# =========================

def generate_image_with_flux() -> str:
    print("Запускаю генерацию изображения через FLUX Kontext...")

    input_data = {
        "prompt": FLUX_PROMPT,
        "input_image": SOURCE_IMAGE_URL,
        "output_format": "jpg",
    }

    output = replicate.run(
        "black-forest-labs/flux-kontext-pro",
        input=input_data,
    )

    # В Replicate FileOutput обычно поддерживает .url и .read()
    image_url = output.url
    print(f"Изображение готово: {image_url}")

    image_path = OUTPUT_DIR / "output.jpg"
    with open(image_path, "wb") as file:
        file.write(output.read())

    print(f"Изображение сохранено: {image_path}")
    return image_url


# =========================
# Шаг 2. Отправка изображения в YES AI на оживление
# =========================

def create_animation_task(image_url: str) -> int:
    print("Отправляю изображение в YES AI на оживление...")

    headers = {
        "Authorization": f"Bearer {YES_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "version": YES_VERSION,
        "duration": YES_DURATION,
        "image_url": image_url,
        "prompt": ANIMATE_PROMPT,
        "final_frame_url": "",
        "dimensions": YES_DIMENSIONS,
        "customer_id": YES_CUSTOMER_ID,
    }

    response = requests.post(
        YES_CREATE_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise RuntimeError(f"YES AI вернул ошибку: {data}")

    try:
        task_id = data["results"]["animation_data"]["id"]
    except KeyError as e:
        raise RuntimeError(f"Не удалось получить id задания из ответа YES AI: {data}") from e

    print(f"Задание создано. ID: {task_id}")
    return task_id


# =========================
# Шаг 3. Ожидание результата с лоадером
# =========================

def poll_animation_result(task_id: int) -> str:
    headers = {
        "Authorization": f"Bearer {YES_API_TOKEN}",
        "Content-Type": "application/json",
    }

    status_url = YES_STATUS_URL_TEMPLATE.format(task_id=task_id)
    started_at = time.time()
    step = 0

    print("Ожидаю готовность видео...")

    while True:
        if time.time() - started_at > POLL_TIMEOUT_SEC:
            print()
            raise TimeoutError(
                f"Превышено время ожидания результата ({POLL_TIMEOUT_SEC} сек). "
                f"Проверьте статус позже вручную: {status_url}"
            )

        sys.stdout.write(spinner_message(f"Проверяю статус задания {task_id}", step))
        sys.stdout.flush()
        step += 1

        response = requests.get(status_url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()

        if not data.get("success"):
            print()
            raise RuntimeError(f"Ошибка при проверке статуса YES AI: {data}")

        animation_data = data.get("results", {}).get("animation_data", {})
        status = animation_data.get("status")
        status_description = animation_data.get("status_description", "unknown")
        result_url = animation_data.get("result_url", "")

        # Статусы по твоему примеру:
        # 0 = in queue
        # 2 = completed
        if status == 2 and result_url:
            print("\rВидео готово.                                      ")
            return result_url

        # Если у сервиса есть статус ошибки
        if status in (-1, 3, 4, 5):
            print()
            raise RuntimeError(
                f"Генерация завершилась ошибкой. status={status}, "
                f"status_description={status_description}, response={data}"
            )

        time.sleep(POLL_INTERVAL_SEC)


# =========================
# Шаг 4. Главный сценарий
# =========================

def main():
    try:
        image_url = generate_image_with_flux()

        task_id = create_animation_task(image_url)

        video_url = poll_animation_result(task_id)

        print(f"Ссылка на видео: {video_url}")

        # Опционально: скачать видео на диск
        video_path = OUTPUT_DIR / "result.mp4"
        print("Скачиваю видео...")
        download_file(video_url, video_path)
        print(f"Видео сохранено: {video_path}")

    except Exception as e:
        print(f"\nОшибка: {e}")
        raise


if __name__ == "__main__":
    main()