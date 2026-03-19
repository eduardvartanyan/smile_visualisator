from dotenv import load_dotenv
import os
import logging
from typing import Optional

import requests
import replicate
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, HttpUrl


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
YES_API_TOKEN = os.getenv("YES_API_TOKEN")
BACKEND_API_TOKEN = os.getenv("BACKEND_API_TOKEN")

if not REPLICATE_API_TOKEN:
    raise RuntimeError("REPLICATE_API_TOKEN не найден")

if not YES_API_TOKEN:
    raise RuntimeError("YES_API_TOKEN не найден")

if not BACKEND_API_TOKEN:
    raise RuntimeError("BACKEND_API_TOKEN не найден")


YES_CREATE_URL = "https://api.yesai.su/v2/yesvideo/aniimage/kling"
YES_STATUS_URL_TEMPLATE = "https://api.yesai.su/v2/yesvideo/animations/{task_id}"

YES_CUSTOMER_ID = "ncsehpgt"
YES_VERSION = "2.5"
YES_DURATION = "5"
YES_DIMENSIONS = "16:9"

DEFAULT_EDIT_PROMPT = (
    "natural healthy teeth, subtle smile improvement, "
    "slight reduction of nasolabial folds, natural skin texture, "
    "professional portrait retouching, realistic lighting"
)

DEFAULT_ANIMATE_PROMPT = (
    "The person looks into the camera, smiles naturally, "
    "turns head slightly and nods, realistic skin texture, 4k"
)


app = FastAPI(title="AI Animation Backend")


class GenerateVideoRequest(BaseModel):
    image_url: HttpUrl
    edit_prompt: Optional[str] = DEFAULT_EDIT_PROMPT
    animate_prompt: Optional[str] = DEFAULT_ANIMATE_PROMPT


def check_api_key(x_api_key: str | None):
    if x_api_key != BACKEND_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def generate_image_with_flux(source_image_url: str, prompt: str) -> str:
    logger.info("Start Replicate edit: %s", source_image_url)

    input_data = {
        "prompt": prompt,
        "input_image": source_image_url,
        "output_format": "jpg",
    }

    try:
        output = replicate.run(
            "black-forest-labs/flux-kontext-pro",
            input=input_data,
        )
    except Exception as e:
        logger.exception("Replicate error")
        raise RuntimeError(f"Ошибка Replicate: {e}")

    image_url = output.url
    logger.info("Replicate done: %s", image_url)
    return image_url


def create_animation_task(image_url: str, animate_prompt: str) -> int:
    logger.info("Create YesAI task for image: %s", image_url)

    headers = {
        "Authorization": f"Bearer {YES_API_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "version": YES_VERSION,
        "duration": YES_DURATION,
        "image_url": image_url,
        "prompt": animate_prompt,
        "final_frame_url": "",
        "dimensions": YES_DIMENSIONS,
        "customer_id": YES_CUSTOMER_ID,
    }

    try:
        response = requests.post(
            YES_CREATE_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.exception("YesAI create task error")
        raise RuntimeError(f"Ошибка создания задачи YesAI: {e}")

    if not data.get("success"):
        raise RuntimeError(f"YesAI вернул ошибку: {data}")

    try:
        task_id = data["results"]["animation_data"]["id"]
    except KeyError as e:
        raise RuntimeError(f"Не удалось получить id задачи YesAI: {data}") from e

    logger.info("YesAI task created: %s", task_id)
    return task_id


def get_animation_status(task_id: int) -> dict:
    headers = {
        "Authorization": f"Bearer {YES_API_TOKEN}",
        "Content-Type": "application/json",
    }

    status_url = YES_STATUS_URL_TEMPLATE.format(task_id=task_id)

    try:
        response = requests.get(status_url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.exception("YesAI status check error")
        raise RuntimeError(f"Ошибка проверки статуса YesAI: {e}")

    if not data.get("success"):
        raise RuntimeError(f"YesAI вернул ошибку статуса: {data}")

    animation_data = data.get("results", {}).get("animation_data")
    if not animation_data:
        raise RuntimeError(f"В ответе YesAI нет animation_data: {data}")

    return animation_data


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-video")
def generate_video(
    payload: GenerateVideoRequest,
    x_api_key: str | None = Header(default=None),
):
    check_api_key(x_api_key)

    try:
        generated_image_url = generate_image_with_flux(
            str(payload.image_url),
            payload.edit_prompt or DEFAULT_EDIT_PROMPT,
        )

        yes_task_id = create_animation_task(
            generated_image_url,
            payload.animate_prompt or DEFAULT_ANIMATE_PROMPT,
        )

        return {
            "success": True,
            "yes_task_id": yes_task_id,
            "generated_image_url": generated_image_url,
            "status": "processing",
        }

    except Exception as e:
        logger.exception("generate_video failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/task/{task_id}")
def task_status(
    task_id: int,
    x_api_key: str | None = Header(default=None),
):
    check_api_key(x_api_key)

    try:
        animation_data = get_animation_status(task_id)

        return {
            "success": True,
            "task_id": task_id,
            "status": animation_data.get("status"),
            "status_description": animation_data.get("status_description"),
            "result_url": animation_data.get("result_url", ""),
            "generated_image_url": animation_data.get("image_url", ""),
            "animation_data": animation_data,
        }

    except Exception as e:
        logger.exception("task_status failed")
        raise HTTPException(status_code=500, detail=str(e))